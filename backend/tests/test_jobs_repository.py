from pathlib import Path

from app.core.progress import StageName, StageStatus
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobCreate, JobStatus


def test_create_and_list_job(tmp_path: Path) -> None:
    repo = JobRepository(tmp_path / "app.db")

    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    jobs = repo.list_jobs()

    assert job.filename == "sample.mp4"
    assert job.status == JobStatus.CREATED
    assert len(jobs) == 1
    assert jobs[0].id == job.id
    assert jobs[0].progress[0].name == "upload"


def test_mark_failed_persists_error(tmp_path: Path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())

    repo.mark_failed(job.id, "whisper executable missing")
    updated = repo.get_job(job.id)

    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "whisper executable missing"


def test_update_stage_persists_stage_detail_without_losing_other_stages(tmp_path: Path) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())

    repo.update_stage(
        job.id,
        StageName.TRANSCRIPTION,
        StageStatus.RUNNING,
        detail="Extracting audio",
        percent=15,
        processed=1,
        total=4,
    )
    updated = repo.get_job(job.id)

    transcription = next(stage for stage in updated.progress if stage.name == StageName.TRANSCRIPTION)
    upload = next(stage for stage in updated.progress if stage.name == StageName.UPLOAD)
    assert transcription.status == StageStatus.RUNNING
    assert transcription.detail == "Extracting audio"
    assert transcription.percent == 15
    assert transcription.processed == 1
    assert transcription.total == 4
    assert upload.status == StageStatus.PENDING
