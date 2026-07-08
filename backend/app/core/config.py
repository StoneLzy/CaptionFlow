from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.asr.schemas import AsrBackend
from app.core.paths import (
    default_data_dir,
    default_logs_dir,
    default_models_dir,
    default_settings_path,
    default_sqlite_path,
)
from app.core.preferences import PreferencesStore
from app.whisper.schemas import WhisperTimestampPrecision


class Settings(BaseSettings):
    data_dir: Path = Field(default_factory=default_data_dir)
    sqlite_path: Path = Field(default_factory=default_sqlite_path)
    models_dir: Path = Field(default_factory=default_models_dir)
    logs_dir: Path = Field(default_factory=default_logs_dir)
    settings_path: Path = Field(default_factory=default_settings_path)

    asr_backend: AsrBackend = AsrBackend.WHISPERKIT_SERVER
    mlx_whisper_model: str = "mlx-community/whisper-large-v3-mlx"
    mlx_whisper_model_dir: str = ""
    mlx_whisper_word_timestamps: bool = True
    whisperkit_executable_path: Path = Path()
    whisperkit_cli_workdir: Path = Path()
    whisperkit_model: str = "large-v3-v20240930_626MB"
    whisperkit_model_path: Path = Path()
    whisperkit_host: str = "127.0.0.1"
    whisperkit_startup_timeout_seconds: float = 120.0
    whisperkit_request_timeout_seconds: float = 1800.0
    asr_max_subtitle_chars: int = 42
    asr_max_subtitle_duration_ms: int = 6000
    asr_min_subtitle_duration_ms: int = 800
    asr_max_word_gap_ms: int = 800

    faster_whisper_model: str = "large-v3-turbo"
    faster_whisper_device: str = "cpu"
    faster_whisper_compute_type: str = "int8"
    faster_whisper_vad_filter: bool = True
    faster_whisper_min_silence_duration_ms: int = 500
    faster_whisper_word_timestamps: bool = True
    faster_whisper_beam_size: int = 1
    faster_whisper_cpu_threads: int = 0
    faster_whisper_num_workers: int = 1
    faster_whisper_condition_on_previous_text: bool = False
    faster_whisper_model_dir: str = ""

    whisper_executable_path: str = ""
    whisper_model_path: str = ""
    whisper_timestamp_precision: WhisperTimestampPrecision = WhisperTimestampPrecision.STANDARD

    provider_base_url: str = ""
    provider_api_key: str = ""
    provider_model: str = ""
    provider_timeout_seconds: float = 120.0
    provider_max_retries: int = 2
    translation_batch_size: int = 40
    translation_context_segments: int = 2

    ffmpeg_executable: str = "ffmpeg"
    ffprobe_executable: str = "ffprobe"
    ytdlp_executable: str = "yt-dlp"
    ytdlp_cookies_file: str = ""

    max_upload_bytes: int = 2 * 1024 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", env_prefix="TM_", extra="ignore")


def get_settings() -> Settings:
    environment_settings = Settings()
    preferences = PreferencesStore(environment_settings.settings_path).load()
    return Settings(
        **{
            **environment_settings.model_dump(),
            **preferences.settings_overrides(),
        },
        _env_file=None,
    )
