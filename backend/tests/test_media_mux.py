from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.media.mux import copy_as_input_mp4, find_track_file, mux_video_audio_stream_copy


def test_find_track_file_ignores_sidecar_artifacts(tmp_path: Path) -> None:
    (tmp_path / "input_video.mp4").write_bytes(b"video")
    (tmp_path / "input_video.srt").write_text("1", encoding="utf-8")

    assert find_track_file(tmp_path, "input_video") == tmp_path / "input_video.mp4"


def test_copy_as_input_mp4(tmp_path: Path) -> None:
    source = tmp_path / "muxed.mp4"
    source.write_bytes(b"video")

    target = copy_as_input_mp4(source, tmp_path)

    assert target == tmp_path / "input.mp4"
    assert target.read_bytes() == b"video"


def test_mux_video_audio_stream_copy(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "input_video.mp4"
    audio_path = tmp_path / "input_audio.m4a"
    output_path = tmp_path / "muxed.mp4"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")

    def fake_probe(path: Path) -> set[str]:
        if path == video_path:
            return {"video"}
        if path == audio_path:
            return {"audio"}
        return set()

    monkeypatch.setattr("app.media.mux.probe_stream_types", fake_probe)
    monkeypatch.setattr("app.media.mux.ensure_ffmpeg_available", lambda: None)

    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        output_path.write_bytes(b"muxed")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.media.mux.subprocess.run", fake_run)

    result = mux_video_audio_stream_copy(video_path, audio_path, output_path)

    assert result == output_path
    assert output_path.exists()
    assert captured["command"] == [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
        str(output_path),
    ]


def test_mux_video_audio_stream_copy_shortest(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "input_video.mp4"
    audio_path = tmp_path / "input_audio.m4a"
    output_path = tmp_path / "muxed.mp4"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")

    monkeypatch.setattr(
        "app.media.mux.probe_stream_types",
        lambda path: {"video"} if "video" in path.name else {"audio"},
    )
    monkeypatch.setattr("app.media.mux.ensure_ffmpeg_available", lambda: None)

    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        output_path.write_bytes(b"muxed")
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.media.mux.subprocess.run", fake_run)

    mux_video_audio_stream_copy(video_path, audio_path, output_path, use_shortest=True)

    assert captured["command"][-2:] == ["-shortest", str(output_path)]


def test_mux_video_audio_stream_copy_requires_video_stream(monkeypatch, tmp_path: Path) -> None:
    video_path = tmp_path / "input_video.mp4"
    audio_path = tmp_path / "input_audio.m4a"
    video_path.write_bytes(b"video")
    audio_path.write_bytes(b"audio")

    monkeypatch.setattr("app.media.mux.probe_stream_types", lambda path: {"audio"})
    monkeypatch.setattr("app.media.mux.ensure_ffmpeg_available", lambda: None)

    with pytest.raises(RuntimeError, match="no video stream"):
        mux_video_audio_stream_copy(video_path, audio_path, tmp_path / "muxed.mp4")
