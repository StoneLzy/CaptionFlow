from pathlib import Path

import pytest

from app.whisper.audio import extract_audio_wav, is_audio_file, probe_media_duration_seconds


def test_is_audio_file_detects_supported_extensions() -> None:
    assert is_audio_file(Path("clip.wav"))
    assert not is_audio_file(Path("clip.mp4"))


def test_extract_audio_wav_invokes_ffmpeg(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "audio.wav"
    input_path.write_text("video", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        output_path.write_text("audio", encoding="utf-8")
        return type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    monkeypatch.setattr("app.whisper.audio.subprocess.run", fake_run)

    result = extract_audio_wav(input_path, output_path)

    assert result == output_path
    assert calls[0][0] == "ffmpeg"
    assert str(input_path) in calls[0]
    assert str(output_path) in calls[0]


def test_extract_audio_wav_raises_when_ffmpeg_fails(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    output_path = tmp_path / "audio.wav"
    input_path.write_text("video", encoding="utf-8")

    def fake_run(command, **kwargs):
        return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "ffmpeg failed"})()

    monkeypatch.setattr("app.whisper.audio.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="audio extraction failed"):
        extract_audio_wav(input_path, output_path)


def test_probe_media_duration_seconds_parses_ffprobe_output(tmp_path: Path, monkeypatch) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_text("video", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return type("Result", (), {"returncode": 0, "stdout": "824.123\n", "stderr": ""})()

    monkeypatch.setattr("app.whisper.audio.subprocess.run", fake_run)

    assert probe_media_duration_seconds(input_path) == pytest.approx(824.123)
    assert calls[0][0] == "ffprobe"
    assert str(input_path) in calls[0]


def test_probe_media_duration_seconds_returns_none_when_ffprobe_fails(
    tmp_path: Path, monkeypatch
) -> None:
    input_path = tmp_path / "input.mp4"
    input_path.write_text("video", encoding="utf-8")

    def fake_run(command, **kwargs):
        return type("Result", (), {"returncode": 1, "stdout": "", "stderr": "bad file"})()

    monkeypatch.setattr("app.whisper.audio.subprocess.run", fake_run)

    assert probe_media_duration_seconds(input_path) is None
