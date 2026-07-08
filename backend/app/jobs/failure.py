from uuid import UUID

from app.core.progress import STAGE_ORDER, StageName, StageStatus
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobStatus, JobSummary


class JobCancelledError(Exception):
    pass


def mark_job_failure(repo: JobRepository, job_id: UUID, error_summary: str) -> JobSummary | None:
    try:
        job = repo.get_job(job_id)
    except KeyError:
        return None
    if job.status in (JobStatus.FAILED, JobStatus.CANCELLED):
        return job

    detail = error_summary
    running = [stage for stage in job.progress if stage.status == StageStatus.RUNNING]
    if running:
        repo.update_stage(job_id, running[0].name, StageStatus.FAILED, detail=detail)
    else:
        failed_stage = _infer_failed_stage(job.progress)
        if failed_stage is not None:
            stage = next(item for item in job.progress if item.name == failed_stage)
            if stage.status != StageStatus.FAILED:
                repo.update_stage(job_id, failed_stage, StageStatus.FAILED, detail=detail)

    return repo.mark_failed(job_id, error_summary)


def _infer_failed_stage(progress) -> StageName | None:
    progress_by_name = {stage.name: stage for stage in progress}
    if progress_by_name.get(StageName.TRANSLATION) and progress_by_name[
        StageName.TRANSLATION
    ].status == StageStatus.FAILED:
        return None

    last_finished_index = -1
    for index, stage_name in enumerate(STAGE_ORDER):
        stage = progress_by_name[stage_name]
        if stage.status in (StageStatus.COMPLETED, StageStatus.SKIPPED):
            last_finished_index = index

    next_index = last_finished_index + 1
    if next_index < len(STAGE_ORDER):
        return STAGE_ORDER[next_index]
    return StageName.EXPORT
