import asyncio
import json

import httpx

from app.jobs.schemas import ProviderSettings, TerminologyEntry
from app.subtitles.schemas import SubtitleSegment
from app.translation.parse_response import parse_translation_payload, validate_items
from app.translation.provider import TranslatedSegment, TranslationResult

_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_JSON_RETRY_SUFFIX = "Return valid JSON only. Use this exact shape: {\"items\":[{\"id\":1,\"text\":\"...\"}]}"


class OpenAICompatibleProvider:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        *,
        timeout_seconds: float = 120.0,
        max_retries: int = 2,
        use_structured_output: bool = True,
    ) -> None:
        self.client = client
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.use_structured_output = use_structured_output

    def build_messages(
        self,
        *,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
        system_prompt: str,
        terminology: list[TerminologyEntry],
        context_segments: list[SubtitleSegment] | None = None,
        json_retry: bool = False,
    ) -> list[dict[str, str]]:
        glossary = "\n".join(f"- {entry.source} => {entry.target}" for entry in terminology)
        user_payload = [{"id": segment.index, "text": segment.text} for segment in segments]
        context_payload = [
            {"id": segment.index, "text": segment.text} for segment in (context_segments or [])
        ]
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    system_prompt
                    or (
                        "Translate subtitles faithfully. Preserve cue boundaries: do not merge or "
                        "split segments. Return JSON object {\"items\":[{\"id\":number,\"text\":string},...]}."
                    )
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Source language: {source_language}\n"
                    f"Target language: {target_language}\n"
                    f"Terminology:\n{glossary or '(none)'}\n"
                    f"Prior translated context (read-only):\n"
                    f"{json.dumps(context_payload, ensure_ascii=False)}\n"
                    f"Segments JSON:\n{json.dumps(user_payload, ensure_ascii=False)}"
                ),
            },
        ]
        if json_retry:
            messages.append({"role": "user", "content": _JSON_RETRY_SUFFIX})
        return messages

    async def _post_completion(
        self,
        client: httpx.AsyncClient,
        *,
        settings: ProviderSettings,
        messages: list[dict[str, str]],
    ) -> httpx.Response:
        url = f"{settings.base_url.rstrip('/')}/chat/completions"
        payload: dict = {
            "model": settings.model,
            "messages": messages,
            "temperature": 0.2,
        }
        if self.use_structured_output:
            payload["response_format"] = {"type": "json_object"}

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {settings.api_key}"},
                    json=payload,
                )
                if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code in _RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise RuntimeError("translation request failed without response")

    def _parse_response_content(
        self,
        content: str,
        segments: list[SubtitleSegment],
    ) -> list[TranslatedSegment]:
        items = parse_translation_payload(content)
        validate_items(items, segments)
        return items

    async def translate(
        self,
        *,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
        system_prompt: str,
        terminology: list[TerminologyEntry],
        settings: ProviderSettings,
        context_segments: list[SubtitleSegment] | None = None,
    ) -> TranslationResult:
        if not segments:
            return TranslationResult(items=[], model=settings.model)

        client = self.client or httpx.AsyncClient(timeout=self.timeout_seconds, trust_env=False)
        close_client = self.client is None
        try:
            messages = self.build_messages(
                segments=segments,
                source_language=source_language,
                target_language=target_language,
                system_prompt=system_prompt,
                terminology=terminology,
                context_segments=context_segments,
            )
            try:
                response = await self._post_completion(client, settings=settings, messages=messages)
                content = response.json()["choices"][0]["message"]["content"]
                items = self._parse_response_content(content, segments)
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                retry_messages = self.build_messages(
                    segments=segments,
                    source_language=source_language,
                    target_language=target_language,
                    system_prompt=system_prompt,
                    terminology=terminology,
                    context_segments=context_segments,
                    json_retry=True,
                )
                response = await self._post_completion(
                    client,
                    settings=settings,
                    messages=retry_messages,
                )
                content = response.json()["choices"][0]["message"]["content"]
                items = self._parse_response_content(content, segments)
            return TranslationResult(items=items, model=settings.model)
        finally:
            if close_client:
                await client.aclose()
