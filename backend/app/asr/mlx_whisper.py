import gc
import importlib
from pathlib import Path
from typing import Any

from app.asr.output import write_transcription_outputs
from app.asr.schemas import (
    AsrConfig,
    TranscribeRequest,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from app.core.constants import SourceLanguage


def import_mlx_whisper() -> Any:
    try:
        import mlx_whisper
    except ImportError as exc:
        raise RuntimeError("mlx-whisper is not installed. Run: pip install mlx-whisper") from exc
    return mlx_whisper


def release_mlx_resources() -> None:
    try:
        transcribe_module = importlib.import_module("mlx_whisper.transcribe")
        model_holder = getattr(transcribe_module, "ModelHolder", None)
        if model_holder is not None:
            model_holder.model = None
            model_holder.model_path = None
    except Exception:
        pass

    gc.collect()

    try:
        mx = importlib.import_module("mlx.core")
        metal = getattr(mx, "metal", None)
        clear_cache = getattr(metal, "clear_cache", None) if metal is not None else None
        if clear_cache is not None:
            clear_cache()
    except Exception:
        pass


class MlxWhisperTranscriber:
    def __init__(self, config: AsrConfig) -> None:
        self.config = config

    def _resolve_model_reference(self) -> str:
        model = self.config.mlx_whisper_model.strip()
        if not model:
            raise ValueError("mlx-whisper model is not configured")

        candidate = Path(model).expanduser()
        if candidate.exists():
            return str(candidate.resolve())

        if self.config.mlx_whisper_model_dir:
            cached = Path(self.config.mlx_whisper_model_dir).expanduser() / model
            if cached.exists():
                return str(cached.resolve())

        return model

    def _transcribe_kwargs(self, source_language: SourceLanguage) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "path_or_hf_repo": self._resolve_model_reference(),
            "word_timestamps": self.config.mlx_whisper_word_timestamps,
        }
        if source_language != SourceLanguage.AUTO:
            kwargs["language"] = source_language.value
        return kwargs

    def _normalize_words(self, words: list[dict[str, Any]] | None) -> list[WordTimestamp]:
        normalized: list[WordTimestamp] = []
        for word in words or []:
            start = word.get("start")
            end = word.get("end")
            text = str(word.get("word", "")).strip()
            if start is None or end is None or not text:
                continue
            start_float = float(start)
            end_float = float(end)
            if end_float <= start_float:
                continue
            normalized.append(
                WordTimestamp(
                    word=text,
                    start=start_float,
                    end=end_float,
                    probability=word.get("probability"),
                )
            )
        return normalized

    def _normalize_result(self, raw: dict[str, Any]) -> TranscriptionResult:
        raw_segments = raw.get("segments") or []
        segments: list[TranscriptionSegment] = []
        text_parts: list[str] = []
        for index, segment in enumerate(raw_segments):
            text = str(segment.get("text", "")).strip()
            segments.append(
                TranscriptionSegment(
                    id=int(segment.get("id", index)),
                    start=float(segment.get("start", 0.0)),
                    end=float(segment.get("end", 0.0)),
                    text=text,
                    words=self._normalize_words(segment.get("words")),
                )
            )
            if text:
                text_parts.append(text)

        if not segments:
            raise RuntimeError("mlx-whisper returned no speech segments")

        duration = max(segment.end for segment in segments)
        return TranscriptionResult(
            language=str(raw.get("language") or "unknown"),
            duration=float(raw.get("duration") or duration),
            segments=segments,
            text=str(raw.get("text") or " ".join(text_parts)).strip(),
        )

    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult:
        if not request.audio_path.exists():
            raise FileNotFoundError(f"audio file not found: {request.audio_path}")

        try:
            mlx_whisper = import_mlx_whisper()
        except RuntimeError:
            raise
        except ImportError as exc:
            raise RuntimeError("mlx-whisper is not installed. Run: pip install mlx-whisper") from exc

        try:
            try:
                raw = mlx_whisper.transcribe(
                    str(request.audio_path),
                    **self._transcribe_kwargs(request.source_language),
                )
            except RuntimeError:
                raise
            except Exception as exc:
                raise RuntimeError(f"mlx-whisper transcription failed: {exc}") from exc

            result = self._normalize_result(raw)
            write_transcription_outputs(
                request.output_prefix,
                result,
                self.config.segmentation,
                output_formats=request.output_formats,
                pipeline_requires_srt=request.pipeline_requires_srt,
            )
            return result
        finally:
            release_mlx_resources()
