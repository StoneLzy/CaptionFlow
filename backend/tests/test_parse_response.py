import pytest

from app.subtitles.schemas import SubtitleSegment
from app.translation.parse_response import parse_translation_payload, strip_json_fences, validate_items
from app.translation.provider import TranslatedSegment


def test_strip_json_fences() -> None:
    content = '```json\n{"items":[{"id":1,"text":"hello"}]}\n```'

    assert strip_json_fences(content).startswith('{"items"')


def test_parse_translation_payload_from_object() -> None:
    items = parse_translation_payload('{"items":[{"id":1,"text":"你好"},{"id":2,"text":"世界"}]}')

    assert [item.text for item in items] == ["你好", "世界"]


def test_parse_translation_payload_from_array() -> None:
    items = parse_translation_payload('[{"id":1,"text":"hello"}]')

    assert items[0].id == 1


def test_validate_items_checks_ids_order_and_empty_text() -> None:
    segments = [
        SubtitleSegment(index=1, start_ms=0, end_ms=100, text="a"),
        SubtitleSegment(index=2, start_ms=100, end_ms=200, text="b"),
    ]
    items = [TranslatedSegment(id=2, text="b"), TranslatedSegment(id=1, text="a")]

    with pytest.raises(ValueError, match="out of order"):
        validate_items(items, segments)

    with pytest.raises(ValueError, match="empty"):
        validate_items([TranslatedSegment(id=1, text=""), TranslatedSegment(id=2, text="b")], segments)
