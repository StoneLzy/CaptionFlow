from pathlib import Path
from types import SimpleNamespace

import pytest

from app.asr.mlx_whisper import MlxWhisperTranscriber, release_mlx_resources
from app.asr.schemas import AsrConfig, TranscribeRequest
from app.core.constants import SourceLanguage


def test_mlx_whisper_transcriber_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    calls: list[dict] = []

    def fake_transcribe(path: str, **kwargs):
        calls.append({"path": path, **kwargs})
        return {
            "language": "ja",
            "text": "こんにちは 世界。",
            "segments": [
                {
                    "id": 0,
                    "start": 0.32,
                    "end": 1.20,
                    "text": "こんにちは 世界。",
                    "words": [
                        {
                            "word": "こんにちは",
                            "start": 0.32,
                            "end": 0.80,
                            "probability": 0.95,
                        },
                        {"word": "世界。", "start": 0.82, "end": 1.20, "probability": 0.93},
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=fake_transcribe),
    )

    transcriber = MlxWhisperTranscriber(AsrConfig())
    result = transcriber.transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=tmp_path / "transcript",
            source_language=SourceLanguage.JAPANESE,
        )
    )

    assert calls[0]["path"] == str(audio_path)
    assert calls[0]["path_or_hf_repo"] == "mlx-community/whisper-large-v3-mlx"
    assert calls[0]["language"] == "ja"
    assert calls[0]["word_timestamps"] is True
    assert result.language == "ja"
    assert result.segments[0].words[0].start == 0.32
    assert (
        "00:00:00,320 --> 00:00:01,200"
        in (tmp_path / "transcript.srt").read_text(encoding="utf-8")
    )


def test_mlx_whisper_transcriber_releases_mlx_resources_after_success(
    tmp_path: Path, monkeypatch
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    released: list[bool] = []

    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(
            transcribe=lambda path, **kwargs: {
                "language": "en",
                "text": "Hello",
                "segments": [{"start": 0.0, "end": 0.5, "text": "Hello"}],
            }
        ),
    )
    monkeypatch.setattr("app.asr.mlx_whisper.release_mlx_resources", lambda: released.append(True))

    MlxWhisperTranscriber(AsrConfig()).transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=tmp_path / "transcript",
        )
    )

    assert released == [True]


def test_mlx_whisper_transcriber_omits_auto_language(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    calls: list[dict] = []

    def fake_transcribe(path: str, **kwargs):
        calls.append(kwargs)
        return {
            "language": "en",
            "text": "Hello",
            "segments": [{"start": 0.0, "end": 0.5, "text": "Hello"}],
        }

    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=fake_transcribe),
    )

    MlxWhisperTranscriber(AsrConfig()).transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=tmp_path / "transcript",
            source_language=SourceLanguage.AUTO,
        )
    )

    assert "language" not in calls[0]


def test_mlx_whisper_transcriber_raises_readable_error_when_dependency_missing(
    tmp_path: Path, monkeypatch
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")

    def missing_module():
        raise ImportError("No module named mlx_whisper")

    monkeypatch.setattr("app.asr.mlx_whisper.import_mlx_whisper", missing_module)

    with pytest.raises(RuntimeError, match="mlx-whisper is not installed"):
        MlxWhisperTranscriber(AsrConfig()).transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )


def test_mlx_whisper_transcriber_raises_when_segments_empty(
    tmp_path: Path, monkeypatch
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=lambda path, **kwargs: {"segments": [], "text": ""}),
    )

    with pytest.raises(RuntimeError, match="returned no speech segments"):
        MlxWhisperTranscriber(AsrConfig()).transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )


def test_mlx_whisper_transcriber_releases_mlx_resources_after_failure(
    tmp_path: Path, monkeypatch
) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    released: list[bool] = []

    def fail_transcribe(path: str, **kwargs):
        raise ValueError("boom")

    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=fail_transcribe),
    )
    monkeypatch.setattr("app.asr.mlx_whisper.release_mlx_resources", lambda: released.append(True))

    with pytest.raises(RuntimeError, match="mlx-whisper transcription failed"):
        MlxWhisperTranscriber(AsrConfig()).transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )

    assert released == [True]


def test_release_mlx_resources_clears_model_holder_and_metal_cache(monkeypatch) -> None:
    holder = SimpleNamespace(model=object(), model_path="model")
    fake_module = SimpleNamespace(ModelHolder=holder)
    fake_metal = SimpleNamespace(clear_cache_calls=0)
    fake_mx = SimpleNamespace(metal=fake_metal)
    collected: list[bool] = []

    def clear_cache() -> None:
        fake_metal.clear_cache_calls += 1

    fake_metal.clear_cache = clear_cache

    def fake_import(name: str):
        if name == "mlx_whisper.transcribe":
            return fake_module
        if name == "mlx.core":
            return fake_mx
        raise AssertionError(name)

    monkeypatch.setattr("app.asr.mlx_whisper.importlib.import_module", fake_import)
    monkeypatch.setattr("app.asr.mlx_whisper.gc.collect", lambda: collected.append(True))

    release_mlx_resources()

    assert holder.model is None
    assert holder.model_path is None
    assert fake_metal.clear_cache_calls == 1
    assert collected == [True]
