from pathlib import Path

from app.core.config import Settings
from app.core.health import probe_dependencies
from app.media.binaries import command_available, ensure_ffmpeg_available


def test_command_available_accepts_absolute_path(tmp_path: Path) -> None:
    executable = tmp_path / "ffmpeg"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    assert command_available(str(executable)) is True


def test_ensure_ffmpeg_available_uses_configured_executable(tmp_path: Path, monkeypatch) -> None:
    executable = tmp_path / "ffmpeg"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    settings = Settings(ffmpeg_executable=str(executable))
    monkeypatch.setattr("app.media.binaries.get_settings", lambda: settings)
    assert ensure_ffmpeg_available(settings) == str(executable)


def test_probe_dependencies_honors_configured_media_executables(tmp_path: Path) -> None:
    ffmpeg = tmp_path / "ffmpeg"
    ffprobe = tmp_path / "ffprobe"
    ytdlp = tmp_path / "yt-dlp"
    for path in (ffmpeg, ffprobe, ytdlp):
        path.write_text("#!/bin/sh\n", encoding="utf-8")
        path.chmod(0o755)

    whisperkit = tmp_path / "argmax-cli"
    whisperkit.write_text("#!/bin/sh\n", encoding="utf-8")
    whisperkit.chmod(0o755)
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    settings = Settings(
        ffmpeg_executable=str(ffmpeg),
        ffprobe_executable=str(ffprobe),
        ytdlp_executable=str(ytdlp),
        whisperkit_executable_path=whisperkit,
        whisperkit_model_path=model_dir,
    )
    payload = probe_dependencies(settings)
    assert payload["checks"]["ffmpeg"] is True
    assert payload["checks"]["ffprobe"] is True
    assert payload["checks"]["ytdlp"] is True
