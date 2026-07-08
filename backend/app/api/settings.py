from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.asr.whisperkit_runtime import (
    resolve_whisperkit_executable,
    resolve_whisperkit_model_path,
)
from app.core.config import Settings, get_settings
from app.core.preferences import AppPreferences, PreferencesStore
from app.core.secrets import MacOSKeychainSecretStore, resolve_provider_api_key
from app.whisper.dtw import infer_dtw_preset

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    provider_base_url: str | None = None
    provider_model: str | None = None
    provider_api_key: str | None = Field(default=None, max_length=4096)
    clear_provider_api_key: bool = False
    whisperkit_executable_path: str | None = None
    whisperkit_model: str | None = None
    whisperkit_model_path: str | None = None
    onboarding_completed: bool | None = None

    @field_validator("provider_base_url")
    @classmethod
    def validate_provider_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        if normalized and not normalized.startswith(("http://", "https://")):
            raise ValueError("Provider Base URL must start with http:// or https://")
        return normalized

    @field_validator(
        "provider_model",
        "whisperkit_executable_path",
        "whisperkit_model",
        "whisperkit_model_path",
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ProviderTestRequest(BaseModel):
    base_url: str
    model: str
    api_key: str = ""

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("Provider Base URL must start with http:// or https://")
        return normalized


def _settings_payload(
    settings: Settings,
    preferences: AppPreferences,
    secret_store: MacOSKeychainSecretStore,
) -> dict[str, object]:
    model_path = settings.whisper_model_path
    inferred_dtw = infer_dtw_preset(Path(model_path)) if model_path else ""
    keychain_configured = bool(secret_store.read())
    executable = resolve_whisperkit_executable(
        settings.whisperkit_executable_path,
        settings.whisperkit_cli_workdir,
    )
    whisperkit_model_path = resolve_whisperkit_model_path(
        settings.whisperkit_model_path,
        settings.whisperkit_cli_workdir,
        settings.whisperkit_model,
    )
    if keychain_configured:
        api_key_storage = "keychain"
    elif settings.provider_api_key:
        api_key_storage = "environment"
    else:
        api_key_storage = "none"

    return {
        "onboarding_completed": preferences.onboarding_completed,
        "data_dir": str(settings.data_dir),
        "models_dir": str(settings.models_dir),
        "logs_dir": str(settings.logs_dir),
        "asr_backend": settings.asr_backend.value,
        "mlx_whisper_model": settings.mlx_whisper_model,
        "mlx_whisper_model_dir": settings.mlx_whisper_model_dir,
        "mlx_whisper_word_timestamps": settings.mlx_whisper_word_timestamps,
        "asr_max_subtitle_chars": settings.asr_max_subtitle_chars,
        "asr_max_subtitle_duration_ms": settings.asr_max_subtitle_duration_ms,
        "asr_min_subtitle_duration_ms": settings.asr_min_subtitle_duration_ms,
        "asr_max_word_gap_ms": settings.asr_max_word_gap_ms,
        "faster_whisper_model": settings.faster_whisper_model,
        "faster_whisper_device": settings.faster_whisper_device,
        "faster_whisper_compute_type": settings.faster_whisper_compute_type,
        "faster_whisper_vad_filter": settings.faster_whisper_vad_filter,
        "faster_whisper_min_silence_duration_ms": (
            settings.faster_whisper_min_silence_duration_ms
        ),
        "faster_whisper_word_timestamps": settings.faster_whisper_word_timestamps,
        "faster_whisper_beam_size": settings.faster_whisper_beam_size,
        "faster_whisper_cpu_threads": settings.faster_whisper_cpu_threads,
        "whisperkit_executable_path": str(
            executable or settings.whisperkit_executable_path
        ),
        "whisperkit_executable_ready": executable is not None,
        "whisperkit_cli_workdir": str(settings.whisperkit_cli_workdir),
        "whisperkit_model": settings.whisperkit_model,
        "whisperkit_model_path": str(
            whisperkit_model_path or settings.whisperkit_model_path
        ),
        "whisperkit_model_ready": whisperkit_model_path is not None,
        "whisperkit_host": settings.whisperkit_host,
        "whisperkit_startup_timeout_seconds": (
            settings.whisperkit_startup_timeout_seconds
        ),
        "whisperkit_request_timeout_seconds": (
            settings.whisperkit_request_timeout_seconds
        ),
        "whisper_executable_path": settings.whisper_executable_path,
        "whisper_model_path": model_path,
        "whisper_timestamp_precision": settings.whisper_timestamp_precision.value,
        "whisper_dtw_preset": inferred_dtw,
        "provider_base_url": settings.provider_base_url,
        "provider_model": settings.provider_model,
        "provider_api_key_configured": keychain_configured
        or bool(settings.provider_api_key),
        "provider_api_key_storage": api_key_storage,
        "provider_timeout_seconds": settings.provider_timeout_seconds,
        "translation_batch_size": settings.translation_batch_size,
        "ytdlp_executable": settings.ytdlp_executable,
        "ytdlp_cookies_configured": bool(settings.ytdlp_cookies_file),
    }


def _read_settings_payload() -> dict[str, object]:
    settings = get_settings()
    preferences = PreferencesStore(settings.settings_path).load()
    return _settings_payload(settings, preferences, MacOSKeychainSecretStore())


@router.get("")
def read_settings() -> dict[str, object]:
    return _read_settings_payload()


@router.patch("")
def update_settings(payload: SettingsUpdate) -> dict[str, object]:
    settings = get_settings()
    store = PreferencesStore(settings.settings_path)
    preferences = store.load()
    secret_store = MacOSKeychainSecretStore()
    update = payload.model_dump(
        exclude_unset=True,
        exclude={"provider_api_key", "clear_provider_api_key"},
    )

    if "provider_api_key" in payload.model_fields_set:
        api_key = (payload.provider_api_key or "").strip()
        if api_key:
            try:
                secret_store.write(api_key)
            except (RuntimeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
    if payload.clear_provider_api_key:
        secret_store.delete()

    next_preferences = preferences.model_copy(update=update)
    store.save(next_preferences)
    return _read_settings_payload()


@router.post("/provider/test")
async def test_provider(payload: ProviderTestRequest) -> dict[str, object]:
    settings = get_settings()
    api_key = payload.api_key.strip() or resolve_provider_api_key(
        settings.provider_api_key
    )
    if not api_key:
        raise HTTPException(status_code=400, detail="Provider API key is not configured")
    if not payload.model.strip():
        raise HTTPException(status_code=400, detail="Provider model is required")

    try:
        async with httpx.AsyncClient(
            timeout=min(settings.provider_timeout_seconds, 30.0),
            trust_env=False,
        ) as client:
            response = await client.get(
                f"{payload.base_url}/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Provider returned HTTP {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not connect to provider: {exc}",
        ) from exc
    return {"ok": True, "model": payload.model.strip()}
