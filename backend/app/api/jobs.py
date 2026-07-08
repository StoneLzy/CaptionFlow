import asyncio
import logging
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import ValidationError

from app.core.config import get_settings
from app.jobs.failure import mark_job_failure
from app.jobs.folder_opener import open_folder
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobDetail, JobRename, JobStatus, JobSummary
from app.jobs.service import JobService
from app.jobs.validation import format_validation_error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_repo() -> JobRepository:
    settings = get_settings()
    return JobRepository(settings.sqlite_path)


def get_service() -> JobService:
    settings = get_settings()
    return JobService(repo=get_repo(), data_dir=settings.data_dir)


def execute_job(job_id: UUID) -> None:
    settings = get_settings()
    service = get_service()
    repo = get_repo()
    try:
        asyncio.run(service.run_job(job_id, settings))
    except Exception as exc:
        logger.exception("Background job %s failed", job_id)
        try:
            job = repo.get_job(job_id)
        except KeyError:
            return
        if job.status == JobStatus.RUNNING:
            mark_job_failure(repo, job_id, str(exc))


def execute_translate_job(job_id: UUID) -> None:
    settings = get_settings()
    service = get_service()
    repo = get_repo()
    try:
        asyncio.run(service.run_translate_job(job_id, settings))
    except Exception as exc:
        logger.exception("Background translate job %s failed", job_id)
        try:
            job = repo.get_job(job_id)
        except KeyError:
            return
        if job.status == JobStatus.RUNNING:
            mark_job_failure(repo, job_id, str(exc))


def _job_or_404(job_id: UUID) -> JobDetail:
    try:
        return get_repo().get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@router.get("")
def list_jobs() -> list[JobSummary]:
    return get_repo().list_jobs()


@router.get("/{job_id}")
def get_job(job_id: UUID) -> JobDetail:
    return _job_or_404(job_id)


@router.patch("/{job_id}")
def rename_job(job_id: UUID, payload: JobRename) -> JobSummary:
    _job_or_404(job_id)
    try:
        return get_service().rename_job(job_id, payload.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: UUID) -> None:
    settings = get_settings()
    repo = get_repo()
    job = _job_or_404(job_id)
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Cannot delete a running job; cancel it first")
    try:
        repo.delete_job(job_id, data_dir=settings.data_dir)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@router.post("/{job_id}/run")
async def run_job(job_id: UUID, background_tasks: BackgroundTasks) -> JobSummary:
    repo = get_repo()
    job = _job_or_404(job_id)
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Job is already running")
    if job.status in (JobStatus.FAILED, JobStatus.COMPLETED, JobStatus.CANCELLED):
        queued_job = repo.reset_job_for_run(job_id)
    else:
        queued_job = repo.update_status(job_id, JobStatus.RUNNING)
    background_tasks.add_task(execute_job, job_id)
    return queued_job


@router.post("/{job_id}/translate")
async def translate_job(job_id: UUID, background_tasks: BackgroundTasks) -> JobSummary:
    repo = get_repo()
    job = _job_or_404(job_id)
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Job is already running")
    if not job.config.enable_translation:
        raise HTTPException(status_code=400, detail="Translation is disabled for this job")
    settings = get_settings()
    service = get_service()
    try:
        service.resolve_subtitle_source_for_job(job_id, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    queued_job = repo.update_status(job_id, JobStatus.RUNNING)
    background_tasks.add_task(execute_translate_job, job_id)
    return queued_job


@router.post("/{job_id}/cancel")
def cancel_job(job_id: UUID) -> JobSummary:
    job = _job_or_404(job_id)
    if job.status != JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Only running jobs can be cancelled")
    return get_repo().cancel_job(job_id)


@router.get("/{job_id}/outputs/{output_key}/download")
def download_job_output(job_id: UUID, output_key: str) -> FileResponse:
    _job_or_404(job_id)
    service = get_service()
    try:
        target = service.resolve_output_path(job_id, output_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Output not found: {output_key}") from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return FileResponse(target, filename=target.name)


@router.get("/{job_id}/logs/{log_name}")
def read_job_log(job_id: UUID, log_name: str) -> PlainTextResponse:
    _job_or_404(job_id)
    service = get_service()
    try:
        content = service.read_job_log(job_id, log_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PlainTextResponse(content)


@router.post("/{job_id}/open-folder")
def open_job_folder(job_id: UUID) -> dict[str, bool]:
    settings = get_settings()
    _job_or_404(job_id)

    job_dir = settings.data_dir / "jobs" / str(job_id)
    if not job_dir.exists() or not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="Job folder not found")

    try:
        open_folder(job_dir)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"opened": True}


@router.post("/video")
async def create_video_job(
    config_json: str = Form("{}"),
    file: UploadFile = File(...),
    audio_file: UploadFile | None = File(None),
) -> JobSummary:
    settings = get_settings()
    service = get_service()
    try:
        return await service.create_video_job(
            file=file,
            config_json=config_json,
            audio_file=audio_file,
            max_upload_bytes=settings.max_upload_bytes,
        )
    except (ValueError, ValidationError) as exc:
        detail = format_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc


@router.post("/video-from-url")
async def create_video_from_url(
    config_json: str = Form("{}"),
) -> JobSummary:
    try:
        return await get_service().create_ytdlp_video_job(config_json=config_json)
    except (ValueError, ValidationError) as exc:
        detail = format_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc


@router.post("/srt")
async def create_srt_job(
    config_json: str = Form("{}"),
    file: UploadFile = File(...),
) -> JobSummary:
    settings = get_settings()
    try:
        return await get_service().create_srt_job(
            file=file,
            config_json=config_json,
            max_upload_bytes=settings.max_upload_bytes,
        )
    except (ValueError, ValidationError) as exc:
        detail = format_validation_error(exc) if isinstance(exc, ValidationError) else str(exc)
        raise HTTPException(status_code=400, detail=detail) from exc
