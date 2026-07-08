import json

import httpx
import pytest

from app.jobs.schemas import ProviderSettings, TerminologyEntry
from app.subtitles.schemas import SubtitleSegment
from app.translation.openai_compatible import OpenAICompatibleProvider


@pytest.mark.asyncio
async def test_provider_returns_aligned_segments() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["model"] == "test-model"
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"items":[{"id":1,"text":"こんにちは"},{"id":2,"text":"世界"}]}'
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(client=client)

    result = await provider.translate(
        segments=[
            SubtitleSegment(index=1, start_ms=0, end_ms=500, text="Hello"),
            SubtitleSegment(index=2, start_ms=600, end_ms=1200, text="world"),
        ],
        source_language="en",
        target_language="ja",
        system_prompt="Translate naturally.",
        terminology=[TerminologyEntry(source="world", target="世界")],
        settings=ProviderSettings(
            base_url="https://example.test/v1",
            api_key="secret",
            model="test-model",
        ),
    )

    assert [item.text for item in result.items] == ["こんにちは", "世界"]


@pytest.mark.asyncio
async def test_provider_parses_json_fences() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '```json\n{"items":[{"id":1,"text":"你好"}]}\n```'
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(client=client)

    result = await provider.translate(
        segments=[SubtitleSegment(index=1, start_ms=0, end_ms=500, text="Hello")],
        source_language="en",
        target_language="zh-Hans",
        system_prompt="",
        terminology=[],
        settings=ProviderSettings(
            base_url="https://example.test/v1",
            api_key="secret",
            model="test-model",
        ),
    )

    assert result.items[0].text == "你好"


@pytest.mark.asyncio
async def test_provider_retries_on_invalid_json() -> None:
    calls = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "not json"}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"items":[{"id":1,"text":"你好"}]}'}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(client=client)

    result = await provider.translate(
        segments=[SubtitleSegment(index=1, start_ms=0, end_ms=500, text="Hello")],
        source_language="en",
        target_language="zh-Hans",
        system_prompt="",
        terminology=[],
        settings=ProviderSettings(
            base_url="https://example.test/v1",
            api_key="secret",
            model="test-model",
        ),
    )

    assert calls["count"] == 2
    assert result.items[0].text == "你好"


@pytest.mark.asyncio
async def test_provider_rejects_mismatched_ids() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"items":[{"id":9,"text":"x"}]}'}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleProvider(client=client, max_retries=0)

    with pytest.raises(ValueError, match="IDs do not match"):
        await provider.translate(
            segments=[SubtitleSegment(index=1, start_ms=0, end_ms=500, text="Hello")],
            source_language="en",
            target_language="zh-Hans",
            system_prompt="",
            terminology=[],
            settings=ProviderSettings(
                base_url="https://example.test/v1",
                api_key="secret",
                model="test-model",
            ),
        )
