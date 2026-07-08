import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from app.core.progress import STAGE_ORDER, StageName, StageProgress, StageStatus
from app.db.models import JobRecord
from app.db.session import make_session_factory
from app.jobs.schemas import JobCreate, JobDetail, JobStatus, JobSummary


def normalize_progress(progress: list[dict]) -> list[dict]:
    existing = {item["name"]: item for item in progress}
    normalized: list[dict] = []
    for stage in STAGE_ORDER:
        if stage.value in existing:
            normalized.append(existing[stage.value])
        else:
            normalized.append(
                StageProgress(name=stage, status=StageStatus.SKIPPED, detail="").model_dump(mode="json")
            )
    return normalized


def initial_progress() -> list[dict]:
    return [
        StageProgress(name=stage, status=StageStatus.PENDING).model_dump(mode="json")
        for stage in STAGE_ORDER
    ]


class JobRepository:
    def __init__(self, sqlite_path: Path) -> None:
        self.session_factory = make_session_factory(sqlite_path)

    def _to_summary(self, record: JobRecord) -> JobSummary:
        return JobSummary(
            id=UUID(record.id),
            filename=record.filename,
            status=JobStatus(record.status),
            created_at=record.created_at,
            updated_at=record.updated_at,
            progress=[StageProgress(**stage) for stage in normalize_progress(record.progress)],
            error_summary=record.error_summary,
            outputs=record.outputs,
        )

    def _to_detail(self, record: JobRecord) -> JobDetail:
        return JobDetail(
            **self._to_summary(record).model_dump(),
            config=JobCreate(**record.config),
        )

    def create_job(self, filename: str, config: JobCreate) -> JobSummary:
        with self.session_factory() as session:
            record = JobRecord(
                filename=filename,
                status=JobStatus.CREATED.value,
                config=config.model_dump(mode="json"),
                progress=initial_progress(),
                outputs={},
            )
            session.add(record)
            session.commit()
            return self._to_summary(record)

    def list_jobs(self) -> list[JobSummary]:
        with self.session_factory() as session:
            records = session.query(JobRecord).order_by(JobRecord.updated_at.desc()).all()
            return [self._to_summary(record) for record in records]

    def get_job(self, job_id: UUID) -> JobDetail:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            return self._to_detail(record)

    def update_filename(self, job_id: UUID, filename: str) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.filename = filename
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def delete_job(self, job_id: UUID, *, data_dir: Path) -> None:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            session.delete(record)
            session.commit()

        job_dir = data_dir / "jobs" / str(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir)

    def reset_job_for_run(self, job_id: UUID) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.status = JobStatus.RUNNING.value
            record.error_summary = None
            record.progress = initial_progress()
            record.outputs = {}
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def cancel_job(self, job_id: UUID) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))

            next_progress: list[dict] = []
            cancelled_detail = "Cancelled by user"
            for stage_data in normalize_progress(record.progress):
                stage = StageProgress(**stage_data)
                if stage.status == StageStatus.RUNNING:
                    stage = stage.model_copy(
                        update={"status": StageStatus.FAILED, "detail": cancelled_detail}
                    )
                next_progress.append(stage.model_dump(mode="json"))

            record.progress = next_progress
            record.status = JobStatus.CANCELLED.value
            record.error_summary = cancelled_detail
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def mark_failed(self, job_id: UUID, error_summary: str) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.status = JobStatus.FAILED.value
            record.error_summary = error_summary
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def update_status(self, job_id: UUID, status: JobStatus) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.status = status.value
            if status == JobStatus.RUNNING:
                record.error_summary = None
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def set_outputs(self, job_id: UUID, outputs: dict[str, str]) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))
            record.outputs = outputs
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)

    def update_stage(
        self,
        job_id: UUID,
        stage_name: StageName,
        status: StageStatus,
        *,
        detail: str = "",
        percent: int | None = None,
        processed: int | None = None,
        total: int | None = None,
        elapsed_seconds: float | None = None,
    ) -> JobSummary:
        with self.session_factory() as session:
            record = session.get(JobRecord, str(job_id))
            if record is None:
                raise KeyError(str(job_id))

            next_progress: list[dict] = []
            for stage_data in normalize_progress(record.progress):
                stage = StageProgress(**stage_data)
                if stage.name == stage_name:
                    stage = stage.model_copy(
                        update={
                            "status": status,
                            "detail": detail,
                            "percent": percent,
                            "processed": processed,
                            "total": total,
                            "elapsed_seconds": elapsed_seconds,
                        }
                    )
                next_progress.append(stage.model_dump(mode="json"))

            record.progress = next_progress
            record.updated_at = datetime.now(timezone.utc)
            session.commit()
            return self._to_summary(record)
