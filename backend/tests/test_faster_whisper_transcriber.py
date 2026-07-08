from pathlib import Path

import pytest

from app.asr.faster_whisper import FasterWhisperTranscriber
from app.asr.output import write_transcription_outputs
from app.asr.schemas import (
    AsrConfig,
    SubtitleSegmentationConfig,
    TranscribeRequest,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from app.asr.segmentation import seconds_to_ms, transcription_to_subtitle_segments
from app.core.constants import SourceLanguage
from app.subtitles.srt import parse_srt


class FakeSegment:
    def __init__(self, *, start: float, end: float, text: str, words=None):
        self.start = start
        self.end = end
        self.text = text
        self.words = words or []


class FakeWord:
    def __init__(self, *, word: str, start: float, end: float, probability: float):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class FakeInfo:
    language = "ja"
    duration = 4.78


class FakeWhisperModel:
    def transcribe(self, audio_path, **kwargs):
        assert Path(audio_path).exists()
        assert kwargs["vad_filter"] is True
        assert kwargs["word_timestamps"] is True
        segments = [
            FakeSegment(
                start=0.32,
                end=4.78,
                text=" こんにちは",
                words=[
                    FakeWord(word="こん", start=0.32, end=0.70, probability=0.91),
                    FakeWord(word="にちは", start=0.71, end=1.05, probability=0.88),
                ],
            )
        ]
        return segments, FakeInfo()


def test_seconds_to_ms_preserves_subsecond_precision() -> None:
    assert seconds_to_ms(0.32) == 320
    assert seconds_to_ms(4.785) == 4785


def test_transcription_to_subtitle_segments_keeps_milliseconds() -> None:
    segments = transcription_to_subtitle_segments(
        TranscriptionResult(
            language="en",
            duration=4.785,
            segments=[
                TranscriptionSegment(id=0, start=0.32, end=4.785, text="hello"),
            ],
            text="hello",
        ),
        SubtitleSegmentationConfig(),
    )

    assert segments[0].start_ms == 320
    assert segments[0].end_ms == 4785


def test_write_transcription_outputs_preserves_fractional_timestamps(tmp_path: Path) -> None:
    prefix = tmp_path / "transcript"
    result = TranscriptionResult(
        language="ja",
        duration=4.78,
        segments=[
            TranscriptionSegment(
                id=0,
                start=0.32,
                end=4.785,
                text="hello",
                words=[WordTimestamp(word="hello", start=0.32, end=0.85, probability=0.9)],
            )
        ],
        text="hello",
    )

    srt_path = write_transcription_outputs(prefix, result, output_formats=["srt", "json"])
    content = srt_path.read_text(encoding="utf-8")

    assert "00:00:00,320 --> 00:00:00,850" in content
    parsed = parse_srt(content)
    assert parsed[0].start_ms == 320
    assert parsed[0].end_ms == 850
    assert prefix.with_suffix(".json").exists()
    assert not prefix.with_suffix(".txt").exists()
    assert not prefix.with_suffix(".md").exists()


def test_faster_whisper_transcriber_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    output_prefix = tmp_path / "transcript"

    monkeypatch.setattr("app.asr.faster_whisper.ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(
        "app.asr.faster_whisper.FasterWhisperTranscriber._load_model",
        lambda self: FakeWhisperModel(),
    )

    transcriber = FasterWhisperTranscriber(AsrConfig())
    result = transcriber.transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=output_prefix,
            source_language=SourceLanguage.JAPANESE,
        )
    )

    assert result.language == "ja"
    assert result.segments[0].words[0].start == 0.32
    srt_content = output_prefix.with_suffix(".srt").read_text(encoding="utf-8")
    assert "00:00:00,320" in srt_content
    assert "00:00:01,050" in srt_content


def test_faster_whisper_transcriber_raises_when_audio_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.asr.faster_whisper.ensure_ffmpeg_available", lambda: None)
    transcriber = FasterWhisperTranscriber(AsrConfig())

    with pytest.raises(FileNotFoundError, match="audio file not found"):
        transcriber.transcribe(
            TranscribeRequest(
                audio_path=tmp_path / "missing.wav",
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )


def test_faster_whisper_transcriber_raises_when_segments_empty(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")

    class EmptyModel:
        def transcribe(self, audio_path, **kwargs):
            return iter([]), FakeInfo()

    monkeypatch.setattr("app.asr.faster_whisper.ensure_ffmpeg_available", lambda: None)
    monkeypatch.setattr(
        "app.asr.faster_whisper.FasterWhisperTranscriber._load_model",
        lambda self: EmptyModel(),
    )

    transcriber = FasterWhisperTranscriber(AsrConfig())
    with pytest.raises(RuntimeError, match="no speech segments"):
        transcriber.transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )
