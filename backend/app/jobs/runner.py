import threading
import time
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

from app.asr.factory import asr_config_from_settings, build_transcriber
from app.asr.schemas import TranscribeRequest
from app.core.config import Settings
from app.core.progress import StageName, StageStatus
from app.jobs.names import sanitize_job_display_name
from app.jobs.repository import JobRepository
from app.jobs.schemas import JobCreate, JobStatus, MediaSource, OutputFormat, ProviderSettings, TranscribeAudioSource
from app.jobs.export_outputs import (
    collect_transcript_outputs,
    export_final_outputs,
    wants_format,
)
from app.jobs.failure import JobCancelledError, mark_job_failure
from app.media.mux import copy_as_input_mp4, find_track_file, mux_video_audio_stream_copy
from app.media.ytdlp import download_media
from app.subtitles.merge import merge_segments
from app.subtitles.schemas import SubtitleSegment
from app.subtitles.srt import format_srt, format_timestamp, parse_srt
from app.translation.batching import chunk_segments, merge_translation_results
from app.translation.provider import TranslatedSegment, TranslationResult
from app.whisper.audio import (
    extract_audio_wav,
    is_audio_file,
    probe_media_duration_seconds,
    probe_stream_types,
)

ESTIMATED_TRANSCRIPTION_REALTIME_FACTOR = 75.0 / 824.0
ESTIMATED_TRANSCRIPTION_MIN_SECONDS = 10.0
ESTIMATED_TRANSCRIPTION_INTERVAL_SECONDS = 1.0
ESTIMATED_TRANSCRIPTION_PROGRESS_CAP = 95


class JobRunner:
    def __init__(
        self,
        *,
        repo: JobRepository,
        data_dir: Path,
        settings: Settings,
        provider,
        default_provider_settings: ProviderSettings | None = None,
    ) -> None:
        self.repo = repo
        self.data_dir = data_dir
        self.settings = settings
        self.provider = provider
        self.default_provider_settings = default_provider_settings or ProviderSettings()

    def ensure_job_active(self, job_id: UUID) -> None:
        try:
            job = self.repo.get_job(job_id)
        except KeyError as exc:
            raise JobCancelledError("Job deleted") from exc
        if job.status == JobStatus.CANCELLED:
            raise JobCancelledError("Cancelled by user")

    def handle_failure(self, job_id: UUID, exc: Exception) -> None:
        if isinstance(exc, JobCancelledError):
            return
        mark_job_failure(self.repo, job_id, str(exc))

    def resolve_provider_settings(self, settings: ProviderSettings) -> ProviderSettings:
        defaults = self.default_provider_settings
        return ProviderSettings(
            base_url=settings.base_url or defaults.base_url,
            api_key=settings.api_key or defaults.api_key,
            model=settings.model or defaults.model,
        )

    def existing_download_outputs(self, job_dir: Path) -> dict[str, str] | None:
        input_mp4 = job_dir / "input.mp4"
        if input_mp4.is_file():
            outputs: dict[str, str] = {"input_mp4": str(input_mp4)}
            log_path = job_dir / "ytdlp.log"
            if log_path.is_file():
                outputs["ytdlp_log"] = str(log_path)
            return outputs

        video_path = find_track_file(job_dir, "input_video")
        audio_path = find_track_file(job_dir, "input_audio")
        if video_path is not None and audio_path is not None:
            outputs = {
                "input_video": str(video_path),
                "input_audio": str(audio_path),
            }
            log_path = job_dir / "ytdlp.log"
            if log_path.is_file():
                outputs["ytdlp_log"] = str(log_path)
            return outputs
        return None

    def existing_transcript_path(self, job_dir: Path, config: JobCreate) -> Path | None:
        output_prefix = job_dir / "transcript"
        pipeline_requires_srt = config.merge_settings.enabled or config.enable_translation
        srt_path = output_prefix.with_suffix(".srt")
        if pipeline_requires_srt:
            return srt_path if srt_path.is_file() else None
        for suffix in (".srt", ".json", ".txt", ".md"):
            path = output_prefix.with_suffix(suffix)
            if path.is_file():
                return path
        return None

    def existing_subtitle_outputs(self, job_dir: Path, config: JobCreate) -> dict[str, str] | None:
        outputs: dict[str, str] = {}
        required: list[tuple[Path, str]] = []

        if config.merge_settings.enabled and wants_format(config, OutputFormat.SRT):
            required.append((job_dir / "merged.srt", "merged_srt"))

        if config.enable_translation:
            if wants_format(config, OutputFormat.SRT):
                required.append((job_dir / "translation.srt", "translation_srt"))
            if wants_format(config, OutputFormat.TXT):
                required.append((job_dir / "bilingual.txt", "bilingual_txt"))
            if wants_format(config, OutputFormat.MD):
                required.append((job_dir / "bilingual.md", "bilingual_md"))

        if not required:
            return None

        for path, key in required:
            if not path.is_file():
                return None
            outputs[key] = str(path)
        return outputs

    def finalize_outputs(self, job_id: UUID, outputs: dict[str, str]) -> dict[str, str]:
        job = self.repo.get_job(job_id)
        job_dir = self.data_dir / "jobs" / str(job_id)
        return export_final_outputs(outputs=outputs, config=job.config, job_dir=job_dir)

    def resolve_transcription_source(self, job_dir: Path, config: JobCreate) -> Path:
        mux = config.track_mux_settings
        if not mux.enabled:
            return job_dir / "input.mp4"

        if mux.transcribe_from == TranscribeAudioSource.EXTERNAL:
            audio_path = find_track_file(job_dir, "input_audio")
            if audio_path is None:
                input_path = job_dir / "input.mp4"
                if input_path.exists() and "audio" in probe_stream_types(input_path):
                    return input_path
                raise FileNotFoundError("External audio file not found for transcription")
            return audio_path

        muxed_path = job_dir / "muxed.mp4"
        if muxed_path.exists():
            return muxed_path
        input_path = job_dir / "input.mp4"
        if input_path.exists():
            return input_path
        raise FileNotFoundError("Muxed video not found for transcription")

    def run_download(self, job_id: UUID, config: JobCreate) -> dict[str, str]:
        job_dir = self.data_dir / "jobs" / str(job_id)
        if config.media_source == MediaSource.UPLOAD:
            self.repo.update_stage(
                job_id,
                StageName.DOWNLOAD,
                StageStatus.SKIPPED,
                detail="Upload source",
                percent=100,
            )
            return {}

        existing_outputs = self.existing_download_outputs(job_dir)
        if existing_outputs is not None:
            self.repo.update_stage(
                job_id,
                StageName.DOWNLOAD,
                StageStatus.COMPLETED,
                detail="Using existing downloaded media",
                percent=100,
            )
            return existing_outputs

        url = config.ytdlp_settings.url.strip()
        if not url:
            raise ValueError("yt-dlp URL is required")

        self.repo.update_stage(
            job_id,
            StageName.DOWNLOAD,
            StageStatus.RUNNING,
            detail="Downloading media",
        )
        self.ensure_job_active(job_id)
        cookies_file = config.ytdlp_settings.cookies_file.strip() or self.settings.ytdlp_cookies_file
        result = download_media(
            url,
            job_dir,
            settings=config.ytdlp_settings,
            executable=self.settings.ytdlp_executable,
            cookies_file=cookies_file,
        )
        self.ensure_job_active(job_id)
        outputs: dict[str, str] = {
            "download_title": result.title,
            "ytdlp_log": str(job_dir / "ytdlp.log"),
        }
        if result.title and not config.job_name.strip():
            try:
                display_name = sanitize_job_display_name(result.title)
                self.repo.update_filename(job_id, display_name)
            except ValueError:
                pass
        if result.merged_by_ytdlp:
            outputs["input_mp4"] = str(result.primary_path)
            detail = f"Downloaded and merged by yt-dlp: {result.title}"
        else:
            outputs["input_video"] = str(result.video_path)
            outputs["input_audio"] = str(result.audio_path)
            detail = f"Downloaded separate tracks: {result.title}"

        self.repo.update_stage(
            job_id,
            StageName.DOWNLOAD,
            StageStatus.COMPLETED,
            detail=detail,
            percent=100,
        )
        return outputs

    def run_track_mux(self, job_id: UUID, job_dir: Path, config: JobCreate) -> dict[str, str]:
        mux = config.track_mux_settings
        input_mp4 = job_dir / "input.mp4"
        video_path = find_track_file(job_dir, "input_video")
        audio_path = find_track_file(job_dir, "input_audio")
        muxed_path = job_dir / "muxed.mp4"

        if mux.enabled and muxed_path.is_file() and input_mp4.is_file():
            self.repo.update_stage(
                job_id,
                StageName.TRACK_MUX,
                StageStatus.COMPLETED,
                detail="Using existing muxed video",
                percent=100,
            )
            return {
                "muxed_mp4": str(muxed_path),
                "input_mp4": str(input_mp4),
            }

        if video_path is None or audio_path is None:
            if input_mp4.exists():
                streams = probe_stream_types(input_mp4)
                if "video" in streams and "audio" in streams:
                    self.repo.update_stage(
                        job_id,
                        StageName.TRACK_MUX,
                        StageStatus.SKIPPED,
                        detail="Merged by yt-dlp",
                        percent=100,
                    )
                    return {"input_mp4": str(input_mp4)}
            if not mux.enabled:
                self.repo.update_stage(
                    job_id,
                    StageName.TRACK_MUX,
                    StageStatus.SKIPPED,
                    detail="Track mux disabled",
                    percent=100,
                )
                return {}
            raise FileNotFoundError("Video and audio files are required for track mux")

        if not mux.enabled:
            self.repo.update_stage(
                job_id,
                StageName.TRACK_MUX,
                StageStatus.SKIPPED,
                detail="Track mux disabled",
                percent=100,
            )
            return {}

        self.repo.update_stage(
            job_id,
            StageName.TRACK_MUX,
            StageStatus.RUNNING,
            detail="Muxing video and audio tracks",
        )
        mux_video_audio_stream_copy(
            video_path,
            audio_path,
            muxed_path,
            use_shortest=mux.use_shortest,
        )
        copy_as_input_mp4(muxed_path, job_dir)
        self.repo.update_stage(
            job_id,
            StageName.TRACK_MUX,
            StageStatus.COMPLETED,
            detail="Track mux complete",
            percent=100,
        )
        return {
            "muxed_mp4": str(muxed_path),
            "input_mp4": str(job_dir / "input.mp4"),
        }

    def resolve_subtitle_source(self, job_dir: Path, config: JobCreate) -> Path:
        if config.merge_settings.enabled:
            for name in ("transcript.srt", "source.srt"):
                path = job_dir / name
                if path.exists():
                    return path
        for name in ("merged.srt", "transcript.srt", "source.srt"):
            path = job_dir / name
            if path.exists():
                return path
        raise FileNotFoundError("No subtitle source found for translation")

    def estimate_transcription_seconds(self, media_duration_seconds: float | None) -> float | None:
        if media_duration_seconds is None:
            return None
        return max(
            ESTIMATED_TRANSCRIPTION_MIN_SECONDS,
            media_duration_seconds * ESTIMATED_TRANSCRIPTION_REALTIME_FACTOR,
        )

    @contextmanager
    def estimated_transcription_progress(
        self, job_id: UUID, media_duration_seconds: float | None
    ) -> Iterator[None]:
        estimated_seconds = self.estimate_transcription_seconds(media_duration_seconds)
        if estimated_seconds is None:
            yield
            return

        stop = threading.Event()

        def update_progress() -> None:
            started_at = time.monotonic()
            while not stop.wait(ESTIMATED_TRANSCRIPTION_INTERVAL_SECONDS):
                elapsed_seconds = time.monotonic() - started_at
                percent = min(
                    ESTIMATED_TRANSCRIPTION_PROGRESS_CAP,
                    max(1, int((elapsed_seconds / estimated_seconds) * 100)),
                )
                try:
                    self.repo.update_stage(
                        job_id,
                        StageName.TRANSCRIPTION,
                        StageStatus.RUNNING,
                        detail="Transcribing audio",
                        percent=percent,
                        elapsed_seconds=elapsed_seconds,
                    )
                except Exception:
                    return

        thread = threading.Thread(target=update_progress, daemon=True)
        thread.start()
        try:
            yield
        finally:
            stop.set()
            thread.join(timeout=ESTIMATED_TRANSCRIPTION_INTERVAL_SECONDS * 2)

    def write_bilingual_outputs(
        self,
        job_dir: Path,
        source_segments: list[SubtitleSegment],
        translated_segments: list[SubtitleSegment],
        config: JobCreate,
    ) -> dict[str, str]:
        outputs: dict[str, str] = {}
        if wants_format(config, OutputFormat.TXT):
            txt_blocks: list[str] = []
            for source, translated in zip(source_segments, translated_segments, strict=True):
                time_range = f"{format_timestamp(source.start_ms)} --> {format_timestamp(source.end_ms)}"
                txt_blocks.append(f"[{source.index}] {time_range}\n{source.text}\n{translated.text}\n")
            txt_path = job_dir / "bilingual.txt"
            txt_path.write_text("\n".join(txt_blocks), encoding="utf-8")
            outputs["bilingual_txt"] = str(txt_path)
        if wants_format(config, OutputFormat.MD):
            md_rows = ["| # | Time | Source | Translation |", "|---:|---|---|---|"]
            for source, translated in zip(source_segments, translated_segments, strict=True):
                time_range = f"{format_timestamp(source.start_ms)} --> {format_timestamp(source.end_ms)}"
                escaped_source = source.text.replace("|", "\\|").replace("\n", "<br>")
                escaped_translation = translated.text.replace("|", "\\|").replace("\n", "<br>")
                md_rows.append(
                    f"| {source.index} | {time_range} | {escaped_source} | {escaped_translation} |"
                )
            md_path = job_dir / "bilingual.md"
            md_path.write_text("\n".join(md_rows) + "\n", encoding="utf-8")
            outputs["bilingual_md"] = str(md_path)
        return outputs

    def transcribe_video(self, job_id: UUID, media_path: Path | None = None) -> Path:
        job_dir = self.data_dir / "jobs" / str(job_id)
        job = self.repo.get_job(job_id)
        existing = self.existing_transcript_path(job_dir, job.config)
        if existing is not None:
            return existing
        input_path = media_path or self.resolve_transcription_source(job_dir, job.config)
        audio_path = input_path
        if not is_audio_file(input_path):
            audio_path = extract_audio_wav(input_path, job_dir / "audio.wav")

        config = asr_config_from_settings(self.settings, job.config)
        transcriber = build_transcriber(config)
        output_prefix = job_dir / "transcript"
        pipeline_requires_srt = (
            job.config.merge_settings.enabled or job.config.enable_translation
        )
        transcriber.transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=job_dir,
                output_prefix=output_prefix,
                source_language=job.config.source_language,
                whisper_settings=job.config.whisper_settings,
                output_formats=[fmt.value for fmt in job.config.output_formats],
                pipeline_requires_srt=pipeline_requires_srt,
            )
        )
        srt_path = output_prefix.with_suffix(".srt")
        if srt_path.exists():
            return srt_path
        for suffix in (".json", ".txt", ".md"):
            path = output_prefix.with_suffix(suffix)
            if path.exists():
                return path
        raise RuntimeError("transcription produced no output files")

    async def translate_segments(
        self,
        *,
        job_id: UUID,
        segments: list[SubtitleSegment],
        job_config: JobCreate,
    ) -> list[TranslatedSegment]:
        batches = chunk_segments(segments, self.settings.translation_batch_size)
        if not batches:
            return []

        provider_settings = self.resolve_provider_settings(job_config.provider_settings)
        batch_results: list[TranslationResult] = []
        translated_segments: list[SubtitleSegment] = []
        total_batches = len(batches)

        for batch_index, batch in enumerate(batches, start=1):
            context = translated_segments[-self.settings.translation_context_segments :]
            processed_before = len(translated_segments)
            self.repo.update_stage(
                job_id,
                StageName.TRANSLATION,
                StageStatus.RUNNING,
                detail=f"Batch {batch_index} of {total_batches}",
                processed=processed_before,
                total=len(segments),
                percent=self._translation_percent(processed_before, len(segments)),
            )
            try:
                result = await self.provider.translate(
                    segments=batch,
                    source_language=job_config.source_language.value,
                    target_language=job_config.target_language.value,
                    system_prompt=job_config.system_prompt,
                    terminology=job_config.terminology,
                    settings=provider_settings,
                    context_segments=context or None,
                )
            except Exception as exc:
                self.repo.update_stage(
                    job_id,
                    StageName.TRANSLATION,
                    StageStatus.FAILED,
                    detail=str(exc),
                )
                raise

            batch_results.append(result)
            source_by_id = {segment.index: segment for segment in batch}
            for item in result.items:
                source = source_by_id.get(item.id)
                if source is None:
                    raise ValueError(f"Translation returned unknown segment id: {item.id}")
                translated_segments.append(source.model_copy(update={"text": item.text}))

            processed = len(translated_segments)
            self.repo.update_stage(
                job_id,
                StageName.TRANSLATION,
                StageStatus.RUNNING,
                detail=f"Batch {batch_index} of {total_batches}",
                processed=processed,
                total=len(segments),
                percent=self._translation_percent(processed, len(segments)),
            )

        return merge_translation_results(batch_results)

    def _translation_percent(self, processed: int, total: int) -> int:
        if total <= 0:
            return 0
        return min(100, max(0, int(processed / total * 100)))

    async def process_subtitles(self, job_id: UUID, srt_path: Path) -> dict[str, str]:
        job_dir = self.data_dir / "jobs" / str(job_id)
        job = self.repo.get_job(job_id)
        existing_outputs = self.existing_subtitle_outputs(job_dir, job.config)
        if existing_outputs is not None:
            self.repo.update_stage(
                job_id,
                StageName.MERGE,
                StageStatus.COMPLETED if job.config.merge_settings.enabled else StageStatus.SKIPPED,
                detail="Using existing merged subtitles"
                if job.config.merge_settings.enabled
                else "Merge disabled",
                percent=100,
            )
            self.repo.update_stage(
                job_id,
                StageName.TRANSLATION,
                StageStatus.COMPLETED if job.config.enable_translation else StageStatus.SKIPPED,
                detail="Using existing translation"
                if job.config.enable_translation
                else "Translation disabled",
                percent=100,
            )
            return existing_outputs

        source_segments = parse_srt(srt_path.read_text(encoding="utf-8"))
        segments = (
            merge_segments(source_segments, job.config.merge_settings)
            if job.config.merge_settings.enabled
            else source_segments
        )

        outputs: dict[str, str] = {}
        if job.config.merge_settings.enabled:
            self.repo.update_stage(job_id, StageName.MERGE, StageStatus.RUNNING, detail="Merging subtitles")
            if wants_format(job.config, OutputFormat.SRT):
                merged_path = job_dir / "merged.srt"
                merged_path.write_text(format_srt(segments), encoding="utf-8")
                outputs["merged_srt"] = str(merged_path)
            self.repo.update_stage(
                job_id,
                StageName.MERGE,
                StageStatus.COMPLETED,
                detail=f"Merged {len(source_segments)} segments into {len(segments)}",
                percent=100,
                processed=len(segments),
                total=len(segments),
            )
        else:
            self.repo.update_stage(
                job_id,
                StageName.MERGE,
                StageStatus.SKIPPED,
                detail="Merge disabled",
                percent=100,
            )

        if not job.config.enable_translation:
            self.repo.update_stage(
                job_id,
                StageName.TRANSLATION,
                StageStatus.SKIPPED,
                detail="Translation disabled",
                percent=100,
            )
            return outputs

        self.repo.update_stage(
            job_id,
            StageName.TRANSLATION,
            StageStatus.RUNNING,
            detail=f"Translating {len(segments)} segments",
            processed=0,
            total=len(segments),
            percent=0,
        )
        translated_items = await self.translate_segments(
            job_id=job_id,
            segments=segments,
            job_config=job.config,
        )
        translated = {item.id: item.text for item in translated_items}
        translated_segments = [
            segment.model_copy(update={"text": translated[segment.index]}) for segment in segments
        ]
        if wants_format(job.config, OutputFormat.SRT):
            translation_path = job_dir / "translation.srt"
            translation_path.write_text(format_srt(translated_segments), encoding="utf-8")
            outputs["translation_srt"] = str(translation_path)
        outputs.update(
            self.write_bilingual_outputs(job_dir, segments, translated_segments, job.config)
        )
        self.repo.update_stage(
            job_id,
            StageName.TRANSLATION,
            StageStatus.COMPLETED,
            detail=f"Translated {len(translated_segments)} segments",
            percent=100,
            processed=len(translated_segments),
            total=len(segments),
        )
        return outputs

    async def run_translate_job(self, job_id: UUID) -> None:
        job_dir = self.data_dir / "jobs" / str(job_id)
        job = self.repo.get_job(job_id)
        if not job.config.enable_translation:
            raise ValueError("Translation is disabled for this job")
        try:
            self.ensure_job_active(job_id)
            self.repo.update_status(job_id, JobStatus.RUNNING)
            self.repo.update_stage(job_id, StageName.UPLOAD, StageStatus.COMPLETED, percent=100)
            self.repo.update_stage(
                job_id,
                StageName.DOWNLOAD,
                StageStatus.SKIPPED,
                detail="Translate-only rerun",
                percent=100,
            )
            self.repo.update_stage(
                job_id,
                StageName.TRACK_MUX,
                StageStatus.SKIPPED,
                detail="Translate-only rerun",
                percent=100,
            )
            self.repo.update_stage(
                job_id,
                StageName.TRANSCRIPTION,
                StageStatus.SKIPPED,
                detail="Translate-only rerun",
                percent=100,
            )
            srt_path = self.resolve_subtitle_source(job_dir, job.config)
            outputs = await self.process_subtitles(job_id, srt_path)
            merged_outputs = dict(self.repo.get_job(job_id).outputs)
            merged_outputs.update(outputs)
            self.repo.update_stage(job_id, StageName.EXPORT, StageStatus.RUNNING, detail="Exporting outputs")
            merged_outputs = self.finalize_outputs(job_id, merged_outputs)
            self.repo.set_outputs(job_id, merged_outputs)
            self.repo.update_stage(job_id, StageName.EXPORT, StageStatus.COMPLETED, percent=100)
            self.repo.update_status(job_id, JobStatus.COMPLETED)
        except Exception as exc:
            self.handle_failure(job_id, exc)
            raise

    async def run_srt_job(self, job_id: UUID) -> None:
        job_dir = self.data_dir / "jobs" / str(job_id)
        source_path = job_dir / "source.srt"
        job = self.repo.get_job(job_id)
        if not job.config.merge_settings.enabled and not job.config.enable_translation:
            raise ValueError("Enable subtitle merge and/or translation for SRT jobs")
        try:
            self.ensure_job_active(job_id)
            self.repo.update_status(job_id, JobStatus.RUNNING)
            self.repo.update_stage(job_id, StageName.UPLOAD, StageStatus.COMPLETED, percent=100)
            self.repo.update_stage(
                job_id,
                StageName.DOWNLOAD,
                StageStatus.SKIPPED,
                detail="SRT upload",
                percent=100,
            )
            self.repo.update_stage(
                job_id,
                StageName.TRACK_MUX,
                StageStatus.SKIPPED,
                detail="SRT upload",
                percent=100,
            )
            self.repo.update_stage(
                job_id,
                StageName.TRANSCRIPTION,
                StageStatus.SKIPPED,
                detail="SRT upload",
                percent=100,
            )
            outputs = await self.process_subtitles(job_id, source_path)
            self.repo.update_stage(job_id, StageName.EXPORT, StageStatus.RUNNING, detail="Exporting outputs")
            outputs = self.finalize_outputs(job_id, outputs)
            self.repo.set_outputs(job_id, outputs)
            self.repo.update_stage(job_id, StageName.EXPORT, StageStatus.COMPLETED, percent=100)
            self.repo.update_status(job_id, JobStatus.COMPLETED)
        except Exception as exc:
            self.handle_failure(job_id, exc)
            raise

    async def run_transcription_job(self, job_id: UUID) -> None:
        job_dir = self.data_dir / "jobs" / str(job_id)
        job = self.repo.get_job(job_id)
        try:
            self.ensure_job_active(job_id)
            self.repo.update_status(job_id, JobStatus.RUNNING)
            if job.config.media_source == MediaSource.UPLOAD:
                self.repo.update_stage(job_id, StageName.UPLOAD, StageStatus.COMPLETED, percent=100)
            else:
                self.repo.update_stage(
                    job_id,
                    StageName.UPLOAD,
                    StageStatus.SKIPPED,
                    detail="URL job",
                    percent=100,
                )
            self.ensure_job_active(job_id)
            download_outputs = self.run_download(job_id, job.config)
            self.ensure_job_active(job_id)
            mux_outputs = self.run_track_mux(job_id, job_dir, job.config)
            self.ensure_job_active(job_id)
            transcription_source = self.resolve_transcription_source(job_dir, job.config)
            existing_transcript = self.existing_transcript_path(job_dir, job.config)
            if existing_transcript is not None:
                transcript_path = existing_transcript
                self.repo.update_stage(
                    job_id,
                    StageName.TRANSCRIPTION,
                    StageStatus.COMPLETED,
                    detail="Using existing transcript",
                    percent=100,
                )
            else:
                self.repo.update_stage(
                    job_id,
                    StageName.TRANSCRIPTION,
                    StageStatus.RUNNING,
                    detail="Transcribing audio",
                )
                media_duration_seconds = probe_media_duration_seconds(transcription_source)
                with self.estimated_transcription_progress(job_id, media_duration_seconds):
                    transcript_path = self.transcribe_video(job_id, transcription_source)
                self.repo.update_stage(
                    job_id,
                    StageName.TRANSCRIPTION,
                    StageStatus.COMPLETED,
                    detail="Transcription complete",
                    percent=100,
                )
            outputs = collect_transcript_outputs(job_dir, job.config)
            outputs.update(download_outputs)
            outputs.update(mux_outputs)
            job = self.repo.get_job(job_id)
            if job.config.merge_settings.enabled or job.config.enable_translation:
                outputs.update(await self.process_subtitles(job_id, transcript_path))
            else:
                self.repo.update_stage(
                    job_id,
                    StageName.MERGE,
                    StageStatus.SKIPPED,
                    detail="Merge disabled",
                    percent=100,
                )
                self.repo.update_stage(
                    job_id,
                    StageName.TRANSLATION,
                    StageStatus.SKIPPED,
                    detail="Translation disabled",
                    percent=100,
                )
            self.repo.update_stage(job_id, StageName.EXPORT, StageStatus.RUNNING, detail="Exporting outputs")
            outputs = self.finalize_outputs(job_id, outputs)
            self.repo.set_outputs(job_id, outputs)
            self.repo.update_stage(job_id, StageName.EXPORT, StageStatus.COMPLETED, percent=100)
            self.repo.update_status(job_id, JobStatus.COMPLETED)
        except Exception as exc:
            self.handle_failure(job_id, exc)
            raise
