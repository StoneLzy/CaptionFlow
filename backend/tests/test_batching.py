import pytest

from app.subtitles.schemas import SubtitleSegment
from app.translation.batching import chunk_segments, merge_translation_results
from app.translation.provider import TranslatedSegment, TranslationResult


def test_chunk_segments_splits_into_batches() -> None:
    segments = [
        SubtitleSegment(index=index, start_ms=0, end_ms=100, text=f"line {index}")
        for index in range(1, 6)
    ]

    batches = chunk_segments(segments, batch_size=2)

    assert len(batches) == 3
    assert [segment.index for segment in batches[0]] == [1, 2]
    assert [segment.index for segment in batches[-1]] == [5]


def test_chunk_segments_returns_empty_for_no_segments() -> None:
    assert chunk_segments([], batch_size=10) == []


def test_chunk_segments_rejects_invalid_batch_size() -> None:
    with pytest.raises(ValueError, match="batch_size"):
        chunk_segments([], batch_size=0)


def test_merge_translation_results_preserves_order() -> None:
    merged = merge_translation_results(
        [
            TranslationResult(
                items=[TranslatedSegment(id=1, text="a"), TranslatedSegment(id=2, text="b")],
                model="test",
            ),
            TranslationResult(items=[TranslatedSegment(id=3, text="c")], model="test"),
        ]
    )

    assert [item.id for item in merged] == [1, 2, 3]
