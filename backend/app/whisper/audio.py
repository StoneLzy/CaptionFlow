import subprocess
from pathlib import Path

from app.media.binaries import (
    ensure_ffmpeg_available,
    ensure_ffprobe_available,
    resolve_ffmpeg_executable,
    resolve_ffprobe_executable,
)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def is_audio_file(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTENSIONS


def probe_stream_types(input_path: Path) -> set[str]:
    ffprobe = ensure_ffprobe_available()
    if not ffprobe:
        return set()
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type",
            "-of",
            "csv=p=0",
            str(input_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def probe_media_duration_seconds(input_path: Path) -> float | None:
    ffprobe = ensure_ffprobe_available()
    if not ffprobe:
        return None
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None
    return duration if duration > 0 else None


def extract_audio_wav(input_path: Path, output_path: Path) -> Path:
    ffmpeg = ensure_ffmpeg_available()
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not output_path.exists():
        details = (result.stderr or result.stdout or "ffmpeg failed to extract audio").strip()
        raise RuntimeError(f"audio extraction failed: {details}")
    return output_path


__all__ = [
    "AUDIO_EXTENSIONS",
    "ensure_ffmpeg_available",
    "ensure_ffprobe_available",
    "extract_audio_wav",
    "is_audio_file",
    "probe_media_duration_seconds",
    "probe_stream_types",
    "resolve_ffmpeg_executable",
    "resolve_ffprobe_executable",
]
