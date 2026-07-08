from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.jobs.schemas import YtdlpFormatPreset, YtdlpSettings
from app.media.ytdlp import (
    build_format_string,
    download_media,
    normalize_download_files,
)


def test_build_format_string_presets() -> None:
    assert build_format_string(YtdlpSettings()) == "bestvideo*+bestaudio/best"
    assert (
        build_format_string(YtdlpSettings(preset=YtdlpFormatPreset.BEST_1080P))
        == "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best[height<=1080]"
    )
    assert (
        build_format_string(YtdlpSettings(preset=YtdlpFormatPreset.BEST_720P))
        == "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]"
    )


def test_build_format_string_custom_requires_value() -> None:
    with pytest.raises(ValueError, match="custom yt-dlp format"):
        build_format_string(YtdlpSettings(preset=YtdlpFormatPreset.CUSTOM))


def test_normalize_download_files_merged(tmp_path: Path, monkeypatch) -> None:
    merged = tmp_path / "ytdlp.mp4"
    merged.write_bytes(b"merged")
    monkeypatch.setattr(
        "app.media.ytdlp.probe_stream_types",
        lambda path: {"video", "audio"},
    )

    result = normalize_download_files(tmp_path)

    assert result.merged_by_ytdlp is True
    assert (tmp_path / "input.mp4").exists()


def test_normalize_download_files_separate(tmp_path: Path, monkeypatch) -> None:
    video = tmp_path / "ytdlp.f137.mp4"
    audio = tmp_path / "ytdlp.f140.m4a"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    def fake_probe(path: Path) -> set[str]:
        if path == video:
            return {"video"}
        if path == audio:
            return {"audio"}
        return set()

    monkeypatch.setattr("app.media.ytdlp.probe_stream_types", fake_probe)

    result = normalize_download_files(tmp_path)

    assert result.merged_by_ytdlp is False
    assert (tmp_path / "input_video.mp4").exists()
    assert (tmp_path / "input_audio.m4a").exists()


def test_download_media_invokes_ytdlp(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        output = tmp_path / "ytdlp.mp4"
        output.write_bytes(b"merged")
        (tmp_path / "ytdlp.info.json").write_text(
            '{"title": "Sample Title"}',
            encoding="utf-8",
        )
        return MagicMock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.media.ytdlp.ensure_ytdlp_available", lambda executable="yt-dlp": None)
    monkeypatch.setattr("app.media.ytdlp.subprocess.run", fake_run)
    monkeypatch.setattr(
        "app.media.ytdlp.probe_stream_types",
        lambda path: {"video", "audio"},
    )

    result = download_media(
        "https://example.com/watch?v=abc",
        tmp_path,
        settings=YtdlpSettings(),
        executable="yt-dlp",
    )

    assert result.title == "Sample Title"
    assert result.merged_by_ytdlp is True
    assert (tmp_path / "input.mp4").exists()
    command = captured["command"]
    assert command[0] == "yt-dlp"
    assert captured["cwd"] == str(tmp_path.resolve())
    assert command[command.index("-o") + 1] == "ytdlp.%(ext)s"
    assert "-f" in command
    assert "bestvideo*+bestaudio/best" in command
    assert "--merge-output-format" in command
    assert "--print" not in command
    assert "--write-info-json" in command
