import subprocess
from pathlib import Path

from app.asr.schemas import AsrBackend
from app.media.binaries import command_available
from app.asr.whisperkit_runtime import (
    resolve_whisperkit_executable,
    resolve_whisperkit_model_path,
)
from app.core.config import Settings


def probe_asr_backend(settings: Settings) -> dict[str, bool | str]:
    backend = settings.asr_backend
    if backend == AsrBackend.MLX_WHISPER:
        return {"backend": backend.value, "ready": bool(settings.mlx_whisper_model)}
    if backend == AsrBackend.FASTER_WHISPER:
        return {"backend": backend.value, "ready": bool(settings.faster_whisper_model)}
    if backend == AsrBackend.WHISPER_CPP:
        executable_ok = bool(settings.whisper_executable_path) and Path(
            settings.whisper_executable_path
        ).is_file()
        model_ok = bool(settings.whisper_model_path) and Path(settings.whisper_model_path).is_file()
        return {
            "backend": backend.value,
            "ready": executable_ok and model_ok,
            "executable_configured": executable_ok,
            "model_configured": model_ok,
        }
    if backend == AsrBackend.WHISPERKIT_SERVER:
        executable = resolve_whisperkit_executable(
            settings.whisperkit_executable_path,
            settings.whisperkit_cli_workdir,
        )
        model_path = resolve_whisperkit_model_path(
            settings.whisperkit_model_path,
            settings.whisperkit_cli_workdir,
            settings.whisperkit_model,
        )
        return {
            "backend": backend.value,
            "ready": executable is not None and model_path is not None,
            "executable_configured": executable is not None,
            "model_configured": model_path is not None,
        }
    return {"backend": backend.value, "ready": False}


def probe_dependencies(settings: Settings) -> dict[str, object]:
    ffmpeg_ok = command_available(settings.ffmpeg_executable)
    ffprobe_ok = command_available(settings.ffprobe_executable)
    ytdlp_ok = command_available(settings.ytdlp_executable)
    asr = probe_asr_backend(settings)
    provider_ready = bool(settings.provider_base_url and settings.provider_model)
    checks = {
        "ffmpeg": ffmpeg_ok,
        "ffprobe": ffprobe_ok,
        "ytdlp": ytdlp_ok,
        "asr": asr,
        "translation_provider": provider_ready,
    }
    ok = ffmpeg_ok and ffprobe_ok and bool(asr.get("ready"))
    return {"status": "ok" if ok else "degraded", "checks": checks}


def run_version_probe(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr or "").strip()
    return output.splitlines()[0] if output else None
