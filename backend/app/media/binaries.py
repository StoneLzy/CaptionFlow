import os
import shutil
from pathlib import Path

from app.core.config import Settings, get_settings


def command_available(executable: str) -> bool:
    path = Path(executable)
    if path.is_file() and os.access(path, os.X_OK):
        return True
    return shutil.which(executable) is not None


def resolve_ffmpeg_executable(settings: Settings | None = None) -> str:
    return (settings or get_settings()).ffmpeg_executable


def resolve_ffprobe_executable(settings: Settings | None = None) -> str:
    return (settings or get_settings()).ffprobe_executable


def ensure_ffmpeg_available(settings: Settings | None = None) -> str:
    executable = resolve_ffmpeg_executable(settings)
    if not command_available(executable):
        raise RuntimeError(
            "ffmpeg is not installed or not on PATH. Install ffmpeg before transcribing audio."
        )
    return executable


def ensure_ffprobe_available(settings: Settings | None = None) -> str:
    executable = resolve_ffprobe_executable(settings)
    if not command_available(executable):
        return ""
    return executable
