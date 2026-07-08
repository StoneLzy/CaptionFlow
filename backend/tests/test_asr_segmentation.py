from app.asr.schemas import (
    SubtitleSegmentationConfig,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from app.asr.segmentation import transcription_to_subtitle_segments


def make_result(words: list[WordTimestamp]) -> TranscriptionResult:
    return TranscriptionResult(
        language="en",
        duration=10.0,
        segments=[
            TranscriptionSegment(
                id=0,
                start=words[0].start,
                end=words[-1].end,
                text=" ".join(word.word for word in words),
                words=words,
            )
        ],
        text=" ".join(word.word for word in words),
    )


def test_segments_from_word_timestamps_preserve_word_bounds() -> None:
    result = make_result(
        [
            WordTimestamp(word="Hello", start=0.32, end=0.70),
            WordTimestamp(word="world.", start=0.72, end=1.05),
        ]
    )

    segments = transcription_to_subtitle_segments(result, SubtitleSegmentationConfig())

    assert len(segments) == 1
    assert segments[0].start_ms == 320
    assert segments[0].end_ms == 1050
    assert segments[0].text == "Hello world."


def test_segments_split_on_large_word_gap() -> None:
    result = make_result(
        [
            WordTimestamp(word="First", start=0.0, end=0.4),
            WordTimestamp(word="line.", start=0.5, end=0.8),
            WordTimestamp(word="Second", start=2.0, end=2.4),
            WordTimestamp(word="line.", start=2.5, end=3.0),
        ]
    )

    segments = transcription_to_subtitle_segments(
        result,
        SubtitleSegmentationConfig(max_word_gap_ms=800),
    )

    assert [segment.text for segment in segments] == ["First line.", "Second line."]


def test_segments_split_before_exceeding_max_chars() -> None:
    result = make_result(
        [
            WordTimestamp(word="One", start=0.0, end=0.2),
            WordTimestamp(word="two", start=0.3, end=0.5),
            WordTimestamp(word="three", start=0.6, end=0.8),
        ]
    )

    segments = transcription_to_subtitle_segments(
        result,
        SubtitleSegmentationConfig(max_chars=7),
    )

    assert [segment.text for segment in segments] == ["One two", "three"]


def test_segments_fall_back_to_model_segments_without_words() -> None:
    result = TranscriptionResult(
        language="en",
        duration=1.25,
        segments=[TranscriptionSegment(id=0, start=0.32, end=1.25, text="Fallback")],
        text="Fallback",
    )

    segments = transcription_to_subtitle_segments(result, SubtitleSegmentationConfig())

    assert segments[0].start_ms == 320
    assert segments[0].end_ms == 1250
    assert segments[0].text == "Fallback"
