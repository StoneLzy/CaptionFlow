import json
import re

from app.subtitles.schemas import SubtitleSegment
from app.translation.provider import TranslatedSegment

_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def strip_json_fences(content: str) -> str:
    stripped = content.strip()
    match = _FENCE_PATTERN.match(stripped)
    if match:
        return match.group(1).strip()
    return stripped


def parse_translation_payload(content: str) -> list[TranslatedSegment]:
    cleaned = strip_json_fences(content)
    payload = json.loads(cleaned)
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("items")
        if raw_items is None:
            raw_items = payload.get("segments", [])
    else:
        raise ValueError("translation payload must be a JSON object or array")

    items: list[TranslatedSegment] = []
    for raw_item in raw_items:
        items.append(
            TranslatedSegment(
                id=int(raw_item["id"]),
                text=str(raw_item["text"]).strip(),
            )
        )
    return items


def validate_items(
    items: list[TranslatedSegment],
    expected_segments: list[SubtitleSegment],
) -> None:
    expected_ids = [segment.index for segment in expected_segments]
    actual_ids = [item.id for item in items]
    if set(actual_ids) != set(expected_ids):
        raise ValueError("translation result IDs do not match input segment IDs")
    if actual_ids != expected_ids:
        raise ValueError("translation result IDs are out of order")
    for item in items:
        if not item.text:
            raise ValueError(f"translation for segment {item.id} is empty")
