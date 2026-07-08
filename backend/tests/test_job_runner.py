from pathlib import Path
import time

import pytest

from app.core.progress import StageName, StageStatus
from app.asr.output import write_transcription_outputs
from app.asr.schemas import TranscriptionResult, TranscriptionSegment
from app.jobs.repository import JobRepository
from app.jobs.runner import JobRunner
from app.jobs.schemas import JobCreate, JobStatus, MediaSource, TrackMuxSettings, TranscribeAudioSource, YtdlpSettings
from app.core.config import Settings


class FakeTranscriber:
    def transcribe(self, request):
        result = TranscriptionResult(
            language="en",
            duration=1.05,
            segments=[
                TranscriptionSegment(id=0, start=0.32, end=1.05, text="Hello"),
            ],
            text="Hello",
        )
        write_transcription_outputs(
            request.output_prefix,
            result,
            output_formats=request.output_formats,
            pipeline_requires_srt=request.pipeline_requires_srt,
        )
        return result


class SlowFakeTranscriber(FakeTranscriber):
    def transcribe(self, request):
        time.sleep(0.05)
        return super().transcribe(request)


class FakeProvider:
    async def translate(self, **kwargs):
        from app.translation.provider import TranslatedSegment, TranslationResult

        segments = kwargs.get("segments", [])
        return TranslationResult(
            items=[TranslatedSegment(id=segment.index, text=f"译{segment.text}") for segment in segments],
            model="fake",
        )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path,
        sqlite_path=tmp_path / "app.db",
        asr_backend="faster_whisper",
    )


@pytest.mark.asyncio
async def test_runner_creates_translation_outputs(tmp_path: Path, settings: Settings, monkeypatch) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="video.mp4", config=JobCreate())
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input.mp4").write_text("video", encoding="utf-8")

    monkeypatch.setattr(
        "app.jobs.runner.extract_audio_wav",
        lambda input_path, output_path: output_path,
    )
    monkeypatch.setattr("app.jobs.runner.build_transcriber", lambda config: FakeTranscriber())

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    progress = {stage.name: stage for stage in updated.progress}
    assert progress["upload"].status == "completed"
    assert progress["transcription"].status == "completed"
    assert progress["merge"].status == "skipped"
    assert progress["translation"].status == "completed"
    assert progress["translation"].processed == 1
    assert progress["translation"].total == 1
    assert progress["export"].status == "completed"
    assert (job_dir / "translation.srt").read_text(encoding="utf-8").strip().endswith("译Hello")
    assert "transcript_srt" in updated.outputs
    assert "translation_srt" in updated.outputs
    assert "transcript_json" not in updated.outputs
    assert "transcript_txt" not in updated.outputs
    assert "transcript_md" not in updated.outputs
    assert not (job_dir / "transcript.json").exists()
    assert "00:00:00,320" in (job_dir / "transcript.srt").read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_runner_completes_srt_only_job(tmp_path: Path, settings: Settings) -> None:
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
        provider=FakeProvider(),
    )
    await runner.run_srt_job(job.id)

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    assert (job_dir / "translation.srt").exists()


@pytest.mark.asyncio
async def test_runner_transcription_only_skips_translation(
    tmp_path: Path, settings: Settings, monkeypatch
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
    monkeypatch.setattr("app.jobs.runner.build_transcriber", lambda config: FakeTranscriber())

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    assert "transcript_srt" in updated.outputs
    assert "translation_srt" not in updated.outputs
    assert not (job_dir / "transcript.txt").exists()
    assert not (job_dir / "transcript.md").exists()
    assert not (job_dir / "transcript.json").exists()


@pytest.mark.asyncio
async def test_runner_exports_final_outputs_to_custom_directory(
    tmp_path: Path, settings: Settings, monkeypatch
) -> None:
    repo = JobRepository(tmp_path / "app.db")
    export_dir = tmp_path / "chosen-output"
    job = repo.create_job(
        filename="video.mp4",
        config=JobCreate(enable_translation=False, output_directory=str(export_dir)),
    )
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input.mp4").write_text("video", encoding="utf-8")

    monkeypatch.setattr(
        "app.jobs.runner.extract_audio_wav",
        lambda input_path, output_path: output_path,
    )
    monkeypatch.setattr("app.jobs.runner.build_transcriber", lambda config: FakeTranscriber())

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    exported = export_dir / "transcript.srt"
    assert exported.exists()
    assert (job_dir / "transcript.srt").exists()
    assert updated.outputs["transcript_srt"] == str(exported)
    assert updated.output_directory == str(export_dir)


@pytest.mark.asyncio
async def test_runner_retry_reuses_existing_ytdlp_download(
    tmp_path: Path, settings: Settings, monkeypatch
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
    (job_dir / "input.mp4").write_bytes(b"downloaded")

    def fail_download(*args, **kwargs):
        raise AssertionError("download should not run when input.mp4 already exists")

    def fake_transcribe(self, job_id, media_path=None):
        srt_path = tmp_path / "jobs" / str(job_id) / "transcript.srt"
        srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        return srt_path

    monkeypatch.setattr("app.jobs.runner.download_media", fail_download)
    monkeypatch.setattr(
        "app.jobs.runner.probe_stream_types",
        lambda path: {"video", "audio"},
    )
    monkeypatch.setattr(JobRunner, "transcribe_video", fake_transcribe)

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert progress["download"].status == "completed"
    assert progress["download"].detail == "Using existing downloaded media"
    assert updated.outputs["input_mp4"] == str(job_dir / "input.mp4")


@pytest.mark.asyncio
async def test_runner_updates_estimated_transcription_progress(
    tmp_path: Path, settings: Settings, monkeypatch
) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(
        filename="video.mp4",
        config=JobCreate(enable_translation=False),
    )
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input.mp4").write_text("video", encoding="utf-8")
    running_percents: list[int] = []
    original_update_stage = repo.update_stage

    def track_update_stage(job_id, stage_name, status, **kwargs):
        if (
            stage_name == StageName.TRANSCRIPTION
            and status == StageStatus.RUNNING
            and kwargs.get("percent") is not None
        ):
            running_percents.append(kwargs["percent"])
        return original_update_stage(job_id, stage_name, status, **kwargs)

    monkeypatch.setattr(repo, "update_stage", track_update_stage)
    monkeypatch.setattr(
        "app.jobs.runner.extract_audio_wav",
        lambda input_path, output_path: output_path,
    )
    monkeypatch.setattr("app.jobs.runner.build_transcriber", lambda config: SlowFakeTranscriber())
    monkeypatch.setattr("app.jobs.runner.probe_media_duration_seconds", lambda input_path: 1.0)
    monkeypatch.setattr("app.jobs.runner.ESTIMATED_TRANSCRIPTION_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr("app.jobs.runner.ESTIMATED_TRANSCRIPTION_REALTIME_FACTOR", 0.05)
    monkeypatch.setattr("app.jobs.runner.ESTIMATED_TRANSCRIPTION_MIN_SECONDS", 0.01)

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert running_percents
    assert max(running_percents) <= 95
    assert progress["transcription"].status == "completed"
    assert progress["transcription"].percent == 100


@pytest.mark.asyncio
async def test_runner_merge_only_srt_job(tmp_path: Path, settings: Settings) -> None:
    from app.jobs.schemas import MergeSettings

    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(
        filename="source.srt",
        config=JobCreate(enable_translation=False, merge_settings=MergeSettings(enabled=True)),
    )
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "source.srt").write_text(
        "1\n00:00:00,000 --> 00:00:00,500\nHello\n"
        "2\n00:00:00,600 --> 00:00:01,200\nworld\n",
        encoding="utf-8",
    )

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_srt_job(job.id)

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    assert "merged_srt" in updated.outputs
    assert "translation_srt" not in updated.outputs


@pytest.mark.asyncio
async def test_runner_translate_only_job_uses_existing_transcript(
    tmp_path: Path, settings: Settings,
) -> None:
    settings = settings.model_copy(update={"translation_batch_size": 1})
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="video.mp4", config=JobCreate())
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "transcript.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nworld\n",
        encoding="utf-8",
    )
    repo.set_outputs(job.id, {"transcript_srt": str(job_dir / "transcript.srt")})

    class CountingProvider(FakeProvider):
        def __init__(self) -> None:
            self.count = 0

        async def translate(self, **kwargs):
            self.count += 1
            return await super().translate(**kwargs)

    provider = CountingProvider()
    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=provider,
    )
    await runner.run_translate_job(job.id)

    updated = repo.get_job(job.id)
    assert updated.status == JobStatus.COMPLETED
    assert provider.count == 2
    assert "translation_srt" in updated.outputs
    assert "transcript_srt" in updated.outputs
    progress = {stage.name: stage for stage in updated.progress}
    assert progress["transcription"].status == "skipped"
    assert progress["translation"].status == "completed"
    assert progress["translation"].total == 2


@pytest.mark.asyncio
async def test_runner_updates_translation_progress_per_batch(
    tmp_path: Path, settings: Settings,
) -> None:
    settings = settings.model_copy(update={"translation_batch_size": 1})
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(filename="source.srt", config=JobCreate())
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "source.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nHello\n\n"
        "2\n00:00:01,000 --> 00:00:02,000\nworld\n",
        encoding="utf-8",
    )

    class CountingProvider(FakeProvider):
        async def translate(self, **kwargs):
            return await super().translate(**kwargs)

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=CountingProvider(),
    )

    snapshots: list[tuple[int | None, int | None, int | None]] = []
    original_update_stage = repo.update_stage

    def track_update_stage(job_id, stage_name, status, **kwargs):
        if stage_name == StageName.TRANSLATION and status == StageStatus.RUNNING:
            snapshots.append(
                (kwargs.get("percent"), kwargs.get("processed"), kwargs.get("total"))
            )
        return original_update_stage(job_id, stage_name, status, **kwargs)

    repo.update_stage = track_update_stage  # type: ignore[method-assign]
    await runner.run_srt_job(job.id)

    assert snapshots[0] == (0, 0, 2)
    assert snapshots[1] == (0, 0, 2)
    assert snapshots[2] == (50, 1, 2)
    assert snapshots[-1] == (100, 2, 2)


@pytest.mark.asyncio
async def test_runner_track_mux_uses_external_audio_for_transcription(
    tmp_path: Path, settings: Settings, monkeypatch
) -> None:
    repo = JobRepository(tmp_path / "app.db")
    job = repo.create_job(
        filename="video.mp4",
        config=JobCreate(
            enable_translation=False,
            track_mux_settings=TrackMuxSettings(
                enabled=True,
                transcribe_from=TranscribeAudioSource.EXTERNAL,
            ),
        ),
    )
    job_dir = tmp_path / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "input_video.mp4").write_bytes(b"video")
    (job_dir / "input_audio.m4a").write_bytes(b"audio")

    transcribed_from: list[Path] = []

    def fake_mux(video_path, audio_path, output_path, *, use_shortest=False):
        output_path.write_bytes(b"muxed")
        return output_path

    def fake_copy(source, job_dir):
        target = job_dir / "input.mp4"
        target.write_bytes(source.read_bytes())
        return target

    def fake_transcribe(self, job_id, media_path=None):
        transcribed_from.append(media_path)
        srt_path = tmp_path / "jobs" / str(job_id) / "transcript.srt"
        srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        return srt_path

    monkeypatch.setattr("app.jobs.runner.mux_video_audio_stream_copy", fake_mux)
    monkeypatch.setattr("app.jobs.runner.copy_as_input_mp4", fake_copy)
    monkeypatch.setattr(JobRunner, "transcribe_video", fake_transcribe)

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert progress["download"].status == "skipped"
    assert progress["track_mux"].status == "completed"
    assert progress["transcription"].status == "completed"
    assert transcribed_from == [job_dir / "input_audio.m4a"]
    assert (job_dir / "input.mp4").exists()
    assert "muxed_mp4" in updated.outputs


@pytest.mark.asyncio
async def test_runner_ytdlp_download_skips_track_mux_when_merged(
    tmp_path: Path, settings: Settings, monkeypatch
) -> None:
    from app.jobs.schemas import MediaSource, YtdlpSettings

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

    def fake_download(url, output_dir, *, settings, executable="yt-dlp", cookies_file=""):
        input_mp4 = output_dir / "input.mp4"
        input_mp4.write_bytes(b"merged")
        from app.media.ytdlp import YtdlpDownloadResult

        return YtdlpDownloadResult(
            title="Sample Title",
            merged_by_ytdlp=True,
            primary_path=input_mp4,
        )

    def fake_transcribe(self, job_id, media_path=None):
        srt_path = tmp_path / "jobs" / str(job_id) / "transcript.srt"
        srt_path.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n", encoding="utf-8")
        return srt_path

    monkeypatch.setattr("app.jobs.runner.download_media", fake_download)
    monkeypatch.setattr(
        "app.jobs.runner.probe_stream_types",
        lambda path: {"video", "audio"},
    )
    monkeypatch.setattr(JobRunner, "transcribe_video", fake_transcribe)

    runner = JobRunner(
        repo=repo,
        data_dir=tmp_path,
        settings=settings,
        provider=FakeProvider(),
    )
    await runner.run_transcription_job(job.id)

    updated = repo.get_job(job.id)
    progress = {stage.name: stage for stage in updated.progress}
    assert progress["upload"].status == "skipped"
    assert progress["download"].status == "completed"
    assert progress["track_mux"].status == "skipped"
    assert progress["track_mux"].detail == "Merged by yt-dlp"
    assert progress["transcription"].status == "completed"
    assert updated.filename == "Sample Title"
