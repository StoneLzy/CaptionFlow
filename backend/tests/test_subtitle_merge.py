from app.jobs.schemas import MergeSettings
from app.subtitles.merge import merge_segments
from app.subtitles.schemas import SubtitleSegment


def seg(index: int, start: int, end: int, text: str) -> SubtitleSegment:
    return SubtitleSegment(index=index, start_ms=start, end_ms=end, text=text)


def test_merges_short_segment_forward_when_within_limits() -> None:
    merged = merge_segments(
        [
            seg(1, 0, 500, "Hello"),
            seg(2, 650, 1500, "world"),
        ],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=30, max_gap_ms=300),
    )

    assert len(merged) == 1
    assert merged[0].text == "Hello world"
    assert merged[0].start_ms == 0
    assert merged[0].end_ms == 1500


def test_chains_adjacent_short_segments_while_within_limits() -> None:
    merged = merge_segments(
        [
            seg(1, 0, 300, "One"),
            seg(2, 350, 650, "two"),
            seg(3, 700, 1000, "three"),
        ],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=20, max_gap_ms=100),
    )

    assert len(merged) == 1
    assert merged[0].text == "One two three"
    assert merged[0].start_ms == 0
    assert merged[0].end_ms == 1000


def test_does_not_merge_across_large_gap() -> None:
    merged = merge_segments(
        [seg(1, 0, 500, "Hello"), seg(2, 2000, 2600, "world")],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=30, max_gap_ms=300),
    )

    assert len(merged) == 2


def test_does_not_cross_sentence_ending_when_protected() -> None:
    merged = merge_segments(
        [seg(1, 0, 500, "Done."), seg(2, 650, 1500, "Next")],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=30, max_gap_ms=300),
    )

    assert len(merged) == 2


def test_respects_max_chars() -> None:
    merged = merge_segments(
        [seg(1, 0, 500, "A very long phrase"), seg(2, 650, 1500, "continues")],
        MergeSettings(enabled=True, min_duration_ms=800, max_chars=10, max_gap_ms=300),
    )

    assert len(merged) == 2
