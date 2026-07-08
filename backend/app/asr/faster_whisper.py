import os
from pathlib import Path

from app.asr.output import write_transcription_outputs
from app.asr.schemas import (
    AsrConfig,
    TranscribeRequest,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from app.core.constants import SourceLanguage
from app.media.binaries import ensure_ffmpeg_available


class FasterWhisperTranscriber:
    def __init__(self, config: AsrConfig) -> None:
        self.config = config
        self._model = None

    def _load_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Run: pip install faster-whisper"
            ) from exc

        kwargs: dict = {
            "device": self.config.device,
            "compute_type": self.config.compute_type,
            "cpu_threads": self._resolve_cpu_threads(),
            "num_workers": self.config.num_workers,
        }
        if self.config.model_dir:
            kwargs["download_root"] = self.config.model_dir

        model_path = self._resolve_model_reference()
        try:
            self._model = WhisperModel(model_path, **kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"failed to load faster-whisper model '{self.config.model}': {exc}. "
                "Verify the model name/path and local cache permissions."
            ) from exc
        return self._model

    def _resolve_cpu_threads(self) -> int:
        if self.config.cpu_threads > 0:
            return self.config.cpu_threads
        return os.cpu_count() or 4

    def _resolve_model_reference(self) -> str:
        model = self.config.model.strip()
        if not model:
            raise ValueError("faster-whisper model is not configured")

        candidate = Path(model).expanduser()
        if candidate.exists():
            return str(candidate.resolve())

        if self.config.model_dir:
            cached = Path(self.config.model_dir).expanduser() / f"faster-whisper-{model}"
            if cached.exists():
                return str(cached.resolve())
            alt_cached = Path(self.config.model_dir).expanduser() / f"faster-whisper-{model.replace('.', '-')}"
            if alt_cached.exists():
                return str(alt_cached.resolve())

        return model

    def _resolve_language(self, source_language: SourceLanguage) -> str | None:
        if source_language == SourceLanguage.AUTO:
            return None
        return source_language.value

    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult:
        ensure_ffmpeg_available()
        if not request.audio_path.exists():
            raise FileNotFoundError(f"audio file not found: {request.audio_path}")

        try:
            model = self._load_model()
            segments_iter, info = model.transcribe(
                str(request.audio_path),
                language=self._resolve_language(request.source_language),
                vad_filter=self.config.vad_filter,
                vad_parameters={"min_silence_duration_ms": self.config.min_silence_duration_ms},
                word_timestamps=self.config.word_timestamps,
                beam_size=self.config.beam_size,
                condition_on_previous_text=self.config.condition_on_previous_text,
            )
        except FileNotFoundError:
            raise
        except Exception as exc:
            raise RuntimeError(f"faster-whisper transcription failed: {exc}") from exc

        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []
        for segment_id, segment in enumerate(segments_iter):
            text = segment.text.strip()
            words: list[WordTimestamp] = []
            if getattr(segment, "words", None):
                for word in segment.words:
                    words.append(
                        WordTimestamp(
                            word=word.word,
                            start=word.start,
                            end=word.end,
                            probability=getattr(word, "probability", None),
                        )
                    )
            segments.append(
                TranscriptionSegment(
                    id=segment_id,
                    start=segment.start,
                    end=segment.end,
                    text=text,
                    words=words,
                )
            )
            if text:
                text_parts.append(text)

        if not segments:
            raise RuntimeError(
                "faster-whisper returned no speech segments. "
                "Check audio content, VAD settings, or try disabling vad_filter."
            )

        result = TranscriptionResult(
            language=info.language or "unknown",
            duration=float(info.duration or 0.0),
            segments=segments,
            text=" ".join(text_parts),
        )
        write_transcription_outputs(
            request.output_prefix,
            result,
            self.config.segmentation,
            output_formats=request.output_formats,
            pipeline_requires_srt=request.pipeline_requires_srt,
        )
        return result
