import json
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import UploadFile
from pydantic import ValidationError

from app.core.config import Settings
from app.core.progress import StageName, StageStatus
from app.core.secrets import resolve_provider_api_key
from app.jobs.names import sanitize_job_display_name
from app.jobs.repository import JobRepository
from app.jobs.runner import JobRunner
from app.jobs.schemas import JobCreate, JobSummary, MediaSource, ProviderSettings
from app.jobs.validation import (
    ALLOWED_AUDIO_EXTENSIONS,
    ALLOWED_SRT_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    format_validation_error,
    read_upload_with_limit,
    validate_upload_extension,
)
from app.translation.openai_compatible import OpenAICompatibleProvider


def sanitize_job_config(config: JobCreate) -> JobCreate:
    if not config.provider_settings.api_key:
        return config
    return config.model_copy(
        update={
            "provider_settings": config.provider_settings.model_copy(update={"api_key": ""})
        }
    )


class JobService:
    def __init__(self, *, repo: JobRepository, data_dir: Path) -> None:
        self.repo = repo
        self.data_dir = data_dir
        self._http_client: httpx.AsyncClient | None = None

    def parse_config(self, config_json: str) -> JobCreate:
        if not config_json.strip():
            return sanitize_job_config(JobCreate())
        try:
            payload = json.loads(config_json)
            config = JobCreate(**payload)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid config_json: {exc.msg}") from exc
        except ValidationError as exc:
            raise ValueError(format_validation_error(exc)) from exc
        return sanitize_job_config(config)

    async def create_video_job(
        self,
        *,
        file: UploadFile,
        config_json: str,
        audio_file: UploadFile | None = None,
        max_upload_bytes: int,
    ) -> JobSummary:
        config = self.parse_config(config_json)
        if config.media_source != MediaSource.UPLOAD:
            raise ValueError("video upload jobs require media_source=upload")
        if config.track_mux_settings.enabled and audio_file is None:
            raise ValueError("audio file is required when track mux is enabled")

        job = self.repo.create_job(filename=file.filename or "input.mp4", config=config)
        job_dir = self.data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)

        if config.track_mux_settings.enabled:
            video_suffix = validate_upload_extension(
                file.filename, ALLOWED_VIDEO_EXTENSIONS, "Video file"
            )
            video_path = job_dir / f"input_video{video_suffix}"
            video_path.write_bytes(await read_upload_with_limit(file, max_bytes=max_upload_bytes))
            audio_suffix = validate_upload_extension(
                audio_file.filename, ALLOWED_AUDIO_EXTENSIONS, "Audio file"
            )
            audio_path = job_dir / f"input_audio{audio_suffix}"
            audio_path.write_bytes(
                await read_upload_with_limit(audio_file, max_bytes=max_upload_bytes)
            )
        else:
            video_suffix = validate_upload_extension(
                file.filename, ALLOWED_VIDEO_EXTENSIONS, "Video file"
            )
            target = job_dir / f"input{video_suffix}"
            target.write_bytes(await read_upload_with_limit(file, max_bytes=max_upload_bytes))
            if target.name != "input.mp4":
                (job_dir / "input.mp4").write_bytes(target.read_bytes())

        return self.repo.update_stage(job.id, StageName.UPLOAD, StageStatus.COMPLETED, percent=100)

    async def create_ytdlp_video_job(self, *, config_json: str) -> JobSummary:
        config = self.parse_config(config_json)
        if config.media_source != MediaSource.YTDLP:
            raise ValueError("URL jobs require media_source=ytdlp")
        url = config.ytdlp_settings.url.strip()
        if not url:
            raise ValueError("URL is required for yt-dlp jobs")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise ValueError("URL must start with http:// or https://")

        filename = url if len(url) <= 120 else f"{url[:117]}..."
        job = self.repo.create_job(filename=filename, config=config)
        job_dir = self.data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.url").write_text(url, encoding="utf-8")
        return self.repo.update_stage(
            job.id,
            StageName.UPLOAD,
            StageStatus.SKIPPED,
            detail="URL job",
            percent=100,
        )

    async def create_srt_job(
        self,
        *,
        file: UploadFile,
        config_json: str,
        max_upload_bytes: int,
    ) -> JobSummary:
        config = self.parse_config(config_json)
        validate_upload_extension(file.filename, ALLOWED_SRT_EXTENSIONS, "SRT file")
        job = self.repo.create_job(filename=file.filename or "source.srt", config=config)
        job_dir = self.data_dir / "jobs" / str(job.id)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "source.srt").write_bytes(
            await read_upload_with_limit(file, max_bytes=max_upload_bytes)
        )
        return self.repo.update_stage(job.id, StageName.UPLOAD, StageStatus.COMPLETED, percent=100)

    def get_http_client(self, settings: Settings) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=settings.provider_timeout_seconds,
                trust_env=False,
            )
        return self._http_client

    def build_runner(self, settings: Settings) -> JobRunner:
        return JobRunner(
            repo=self.repo,
            data_dir=self.data_dir,
            settings=settings,
            provider=OpenAICompatibleProvider(
                client=self.get_http_client(settings),
                timeout_seconds=settings.provider_timeout_seconds,
                max_retries=settings.provider_max_retries,
            ),
            default_provider_settings=ProviderSettings(
                base_url=settings.provider_base_url,
                api_key=resolve_provider_api_key(settings.provider_api_key),
                model=settings.provider_model,
            ),
        )

    async def run_job(self, job_id: UUID, settings: Settings) -> None:
        job_dir = self.data_dir / "jobs" / str(job_id)
        runner = self.build_runner(settings)
        if (job_dir / "source.srt").exists():
            await runner.run_srt_job(job_id)
            return
        if (
            (job_dir / "input.mp4").exists()
            or list(job_dir.glob("input_video.*"))
            or (job_dir / "source.url").exists()
        ):
            await runner.run_transcription_job(job_id)
            return
        raise FileNotFoundError(f"No input file found for job {job_id}")

    async def run_translate_job(self, job_id: UUID, settings: Settings) -> None:
        runner = self.build_runner(settings)
        await runner.run_translate_job(job_id)

    def resolve_subtitle_source_for_job(self, job_id: UUID, settings: Settings) -> Path:
        job_dir = self.data_dir / "jobs" / str(job_id)
        job = self.repo.get_job(job_id)
        return self.build_runner(settings).resolve_subtitle_source(job_dir, job.config)

    def read_job_log(self, job_id: UUID, log_name: str) -> str:
        allowed = {
            "ytdlp": "ytdlp.log",
            "whisperkit": "whisperkit.stderr",
        }
        if log_name not in allowed:
            raise ValueError(f"Unknown log name: {log_name}")

        job_dir = self.data_dir / "jobs" / str(job_id)
        log_path = job_dir / allowed[log_name]
        if not log_path.is_file():
            raise FileNotFoundError(f"Log file not found: {allowed[log_name]}")
        return log_path.read_text(encoding="utf-8", errors="replace")

    def resolve_output_path(self, job_id: UUID, output_key: str) -> Path:
        job = self.repo.get_job(job_id)
        path_str = job.outputs.get(output_key)
        if not path_str:
            raise KeyError(output_key)

        job_dir = (self.data_dir / "jobs" / str(job_id)).resolve()
        target = Path(path_str).resolve()
        if target != job_dir and job_dir not in target.parents:
            raise ValueError("Output path is outside the job directory")
        if not target.is_file():
            raise FileNotFoundError(path_str)
        return target

    def rename_job(self, job_id: UUID, filename: str) -> JobSummary:
        display_name = sanitize_job_display_name(filename)
        return self.repo.update_filename(job_id, display_name)
