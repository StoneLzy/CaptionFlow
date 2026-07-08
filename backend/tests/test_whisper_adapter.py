from pathlib import Path

import pytest

from app.core.constants import SourceLanguage
from app.whisper.adapter import WhisperCppAdapter
from app.whisper.schemas import WhisperRequest, WhisperTimestampPrecision


def test_builds_whisper_command(tmp_path: Path) -> None:
    exe = tmp_path / "whisper-cli"
    model = tmp_path / "model.bin"
    video = tmp_path / "video.mp4"
    output = tmp_path / "out"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    model.write_text("model", encoding="utf-8")
    video.write_text("video", encoding="utf-8")

    adapter = WhisperCppAdapter()
    command = adapter.build_command(
        WhisperRequest(
            executable_path=exe,
            model_path=model,
            input_path=video,
            output_prefix=output,
            source_language=SourceLanguage.ENGLISH,
        )
    )

    assert str(exe) == command[0]
    assert "-m" in command
    assert str(model) in command
    assert "-l" in command
    assert "en" in command
    assert "-osrt" in command


def test_builds_word_level_timestamp_flags(tmp_path: Path) -> None:
    exe = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3.bin"
    video = tmp_path / "video.wav"
    output = tmp_path / "out"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    model.write_text("model", encoding="utf-8")
    video.write_text("video", encoding="utf-8")

    adapter = WhisperCppAdapter()
    command = adapter.build_command(
        WhisperRequest(
            executable_path=exe,
            model_path=model,
            input_path=video,
            output_prefix=output,
            timestamp_precision=WhisperTimestampPrecision.WORD,
        )
    )

    assert "-ml" in command
    assert "1" in command
    assert "-sow" in command
    assert "--dtw" not in command


def test_builds_word_dtw_timestamp_flags(tmp_path: Path) -> None:
    exe = tmp_path / "whisper-cli"
    model = tmp_path / "ggml-large-v3.bin"
    video = tmp_path / "video.wav"
    output = tmp_path / "out"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    model.write_text("model", encoding="utf-8")
    video.write_text("video", encoding="utf-8")

    adapter = WhisperCppAdapter()
    command = adapter.build_command(
        WhisperRequest(
            executable_path=exe,
            model_path=model,
            input_path=video,
            output_prefix=output,
            timestamp_precision=WhisperTimestampPrecision.WORD_DTW,
        )
    )

    assert "-ml" in command
    assert "-sow" in command
    assert "--dtw" in command
    assert "large.v3" in command


def test_run_raises_when_output_missing(tmp_path: Path, monkeypatch) -> None:
    exe = tmp_path / "whisper-cli"
    model = tmp_path / "model.bin"
    video = tmp_path / "video.wav"
    output = tmp_path / "out"
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    model.write_text("model", encoding="utf-8")
    video.write_text("video", encoding="utf-8")

    def fake_run(command, **kwargs):
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": "failed to read audio"})()

    monkeypatch.setattr("app.whisper.adapter.subprocess.run", fake_run)
    adapter = WhisperCppAdapter()

    with pytest.raises(RuntimeError, match="whisper transcription failed"):
        adapter.run(
            WhisperRequest(
                executable_path=exe,
                model_path=model,
                input_path=video,
                output_prefix=output,
                source_language=SourceLanguage.AUTO,
            )
        )


def test_missing_executable_raises(tmp_path: Path) -> None:
    adapter = WhisperCppAdapter()

    with pytest.raises(FileNotFoundError):
        adapter.validate_paths(tmp_path / "missing", tmp_path / "model.bin")
