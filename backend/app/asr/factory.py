from pathlib import Path
from importlib import import_module

from app.asr.schemas import AsrBackend, AsrConfig, SubtitleSegmentationConfig, Transcriber
from app.asr.whisperkit_server import WhisperKitServerTranscriber
from app.core.config import Settings
from app.jobs.schemas import JobCreate
from app.whisper.schemas import WhisperSettings


def asr_config_from_settings(settings: Settings, job_config: JobCreate | None = None) -> AsrConfig:
    whisper_settings = (
        job_config.whisper_settings if job_config is not None else WhisperSettings()
    )
    return AsrConfig(
        backend=settings.asr_backend,
        model=settings.faster_whisper_model,
        device=settings.faster_whisper_device,
        compute_type=settings.faster_whisper_compute_type,
        vad_filter=settings.faster_whisper_vad_filter,
        min_silence_duration_ms=settings.faster_whisper_min_silence_duration_ms,
        word_timestamps=settings.faster_whisper_word_timestamps,
        beam_size=settings.faster_whisper_beam_size,
        cpu_threads=settings.faster_whisper_cpu_threads,
        num_workers=settings.faster_whisper_num_workers,
        condition_on_previous_text=settings.faster_whisper_condition_on_previous_text,
        model_dir=settings.faster_whisper_model_dir,
        mlx_whisper_model=settings.mlx_whisper_model,
        mlx_whisper_model_dir=settings.mlx_whisper_model_dir,
        mlx_whisper_word_timestamps=settings.mlx_whisper_word_timestamps,
        whisperkit_executable_path=settings.whisperkit_executable_path,
        whisperkit_cli_workdir=settings.whisperkit_cli_workdir,
        whisperkit_model=settings.whisperkit_model,
        whisperkit_model_path=settings.whisperkit_model_path,
        whisperkit_host=settings.whisperkit_host,
        whisperkit_startup_timeout_seconds=settings.whisperkit_startup_timeout_seconds,
        whisperkit_request_timeout_seconds=settings.whisperkit_request_timeout_seconds,
        segmentation=SubtitleSegmentationConfig(
            max_chars=settings.asr_max_subtitle_chars,
            max_duration_ms=settings.asr_max_subtitle_duration_ms,
            min_duration_ms=settings.asr_min_subtitle_duration_ms,
            max_word_gap_ms=settings.asr_max_word_gap_ms,
        ),
        executable_path=Path(settings.whisper_executable_path) if settings.whisper_executable_path else Path(),
        model_path=Path(settings.whisper_model_path) if settings.whisper_model_path else Path(),
        whisper_settings=whisper_settings,
    )


def build_transcriber(config: AsrConfig) -> Transcriber:
    if config.backend == AsrBackend.WHISPERKIT_SERVER:
        return WhisperKitServerTranscriber(config)
    if config.backend == AsrBackend.MLX_WHISPER:
        return import_module("app.asr.mlx_whisper").MlxWhisperTranscriber(config)
    if config.backend == AsrBackend.FASTER_WHISPER:
        return import_module("app.asr.faster_whisper").FasterWhisperTranscriber(config)
    return import_module("app.asr.whisper_cpp").WhisperCppTranscriber(config)
