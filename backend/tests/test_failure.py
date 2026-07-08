from app.core.progress import StageName, StageStatus
from app.jobs.failure import mark_job_failure
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobCreate, JobStatus


def test_mark_job_failure_marks_running_stage(tmp_path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    repo.update_status(job.id, JobStatus.RUNNING)
    repo.update_stage(job.id, StageName.DOWNLOAD, StageStatus.RUNNING, detail="Downloading")

    mark_job_failure(repo, job.id, "download failed")

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "download failed"
    assert progress[StageName.DOWNLOAD].status == StageStatus.FAILED
    assert progress[StageName.EXPORT].status != StageStatus.FAILED


def test_mark_job_failure_infers_next_stage_when_none_running(tmp_path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    repo.update_status(job.id, JobStatus.RUNNING)
    repo.update_stage(job.id, StageName.UPLOAD, StageStatus.COMPLETED, percent=100)

    mark_job_failure(repo, job.id, "missing input")

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert progress[StageName.DOWNLOAD].status == StageStatus.FAILED


def test_mark_job_failure_is_idempotent(tmp_path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    mark_job_failure(repo, job.id, "first failure")
    mark_job_failure(repo, job.id, "second failure")

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "first failure"


def test_mark_job_failure_ignores_deleted_job(tmp_path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    job_id = job.id
    repo.delete_job(job_id, data_dir=tmp_path)

    assert mark_job_failure(repo, job_id, "late failure") is None
