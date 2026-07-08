from pathlib import Path

from fastapi import UploadFile
from pydantic import ValidationError

ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".ts", ".flv"}
ALLOWED_AUDIO_EXTENSIONS = {".m4a", ".aac", ".mp3", ".wav", ".flac", ".ogg", ".opus", ".wma"}
ALLOWED_SRT_EXTENSIONS = {".srt"}


def validate_upload_extension(filename: str | None, allowed: set[str], label: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"{label} must use one of these extensions: {allowed_list}")
    return suffix or next(iter(allowed))


async def read_upload_with_limit(file: UploadFile, *, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValueError(f"Upload exceeds maximum size of {max_bytes // (1024 * 1024)} MB")
        chunks.append(chunk)
    if total == 0:
        raise ValueError("Upload file is empty")
    return b"".join(chunks)


def format_validation_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    location = ".".join(str(part) for part in first.get("loc", ()))
    message = first.get("msg", "Invalid value")
    if location:
        return f"Invalid config_json field '{location}': {message}"
    return f"Invalid config_json: {message}"
