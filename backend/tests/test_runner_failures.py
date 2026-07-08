from pathlib import Path
from uuid import UUID

import pytest

from app.core.progress import StageName, StageStatus
from app.jobs.repository import JobRepository
from app.jobs.runner import JobRunner
from app.jobs.schemas import JobCreate, JobStatus, MediaSource, YtdlpSettings


class FakeProvider:
    async def translate(self, **kwargs):
        raise AssertionError("translate should not run")


class FailingProvider:
    async def translate(self, **kwargs):
        raise RuntimeError("provider unavailable")


@pytest.mark.asyncio
async def test_runner_download_failure_marks_download_stage(
    tmp_path: Path, settings, monkeypatch
) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(
        filename="https://example.com/watch?v=abc",
        config=JobCreate(
            media_source=MediaSource.YTDLP,
            enable_translation=False,
            ytdlp_settings=YtdlpSettings(url="https://example.com/watch?v=abc"),
        ),
    )
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "source.url").write_text("https://example.com/watch?v=abc", encoding="utf-8")

    def fail_download(*args, **kwargs):
        raise RuntimeError("yt-dlp unavailable")

    monkeypatch.setattr("app.jobs.runner.download_media", fail_download)

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )

    with pytest.raises(RuntimeError, match="yt-dlp unavailable"):
        await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "yt-dlp unavailable"
    assert progress[StageName.DOWNLOAD].status == StageStatus.FAILED
    assert progress[StageName.EXPORT].status != StageStatus.FAILED


@pytest.mark.asyncio
async def test_runner_transcription_failure_marks_transcription_stage(
    tmp_path: Path, settings, monkeypatch
) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(
        filename="video.mp4",
        config=JobCreate(enable_translation=False),
    )
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input.mp4").write_text("video", encoding="utf-8")

    monkeypatch.setattr(
        "app.jobs.runner.extract_audio_wav",
        lambda input_path, output_path: output_path,
    )
    monkeypatch.setattr("app.jobs.runner.probe_media_duration_seconds", lambda input_path: 1.0)

    class FailingTranscriber:
        def transcribe(self, request):
            raise RuntimeError("ASR backend crashed")

    monkeypatch.setattr("app.jobs.runner.build_transcriber", lambda config: FailingTranscriber())

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )

    with pytest.raises(RuntimeError, match="ASR backend crashed"):
        await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "ASR backend crashed"
    assert progress[StageName.TRANSCRIPTION].status == StageStatus.FAILED
    assert progress[StageName.EXPORT].status != StageStatus.FAILED


@pytest.mark.asyncio
async def test_runner_translation_failure_marks_translation_stage(
    tmp_path: Path, settings,
) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="source.srt", config=JobCreate())
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "source.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n",
        encoding="utf-8",
    )

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FailingProvider(),
    )

    with pytest.raises(RuntimeError, match="provider unavailable"):
        await runner.run_srt_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "provider unavailable"
    assert progress[StageName.TRANSLATION].status == StageStatus.FAILED
    assert progress[StageName.EXPORT].status != StageStatus.FAILED


def test_execute_job_marks_failed_when_background_task_crashes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    from app.api.jobs import execute_job

    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="sample.mp4", config=JobCreate())
    repo.update_status(job.id, JobStatus.RUNNING)
    repo.update_stage(job.id, StageName.TRANSCRIPTION, StageStatus.RUNNING)

    class BrokenService:
        async def run_job(self, job_id: UUID, settings) -> None:
            raise RuntimeError("background task crashed")

    monkeypatch.setattr("app.api.jobs.get_service", lambda: BrokenService())

    execute_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "background task crashed"
    assert progress[StageName.TRANSCRIPTION].status == StageStatus.FAILED
    assert progress[StageName.EXPORT].status != StageStatus.FAILED


def test_execute_translate_job_marks_failed_when_background_task_crashes(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_DATA_DIR", str(tmp_path))

    from app.api.jobs import execute_translate_job

    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="source.srt", config=JobCreate())
    repo.update_status(job.id, JobStatus.RUNNING)
    repo.update_stage(job.id, StageName.TRANSLATION, StageStatus.RUNNING)

    class BrokenService:
        async def run_translate_job(self, job_id: UUID, settings) -> None:
            raise RuntimeError("translate task crashed")

    monkeypatch.setattr("app.api.jobs.get_service", lambda: BrokenService())

    execute_translate_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert updated.status == JobStatus.FAILED
    assert updated.error_summary == "translate task crashed"
    assert progress[StageName.TRANSLATION].status == StageStatus.FAILED
    assert progress[StageName.EXPORT].status != StageStatus.FAILED
