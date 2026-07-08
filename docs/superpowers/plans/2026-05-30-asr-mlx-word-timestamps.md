# ASR MLX Word Timestamps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `mlx-whisper` as the default local ASR backend and generate subtitles from normalized word timestamps.

**Architecture:** Keep `JobRunner` behind the existing `Transcriber` factory. Add an MLX transcriber that normalizes dict output into `TranscriptionResult`, then route output writing through a shared segmentation module that prefers word timestamps and falls back to model segments.

**Tech Stack:** FastAPI, Pydantic v2, pytest, React/Vite, Vitest, `mlx-whisper`, existing ASR abstractions.

---

## File Structure

- Create `backend/app/asr/mlx_whisper.py`: MLX backend wrapper and result normalization.
- Create `backend/app/asr/segmentation.py`: word timestamp filtering and subtitle segmentation.
- Create `backend/tests/test_mlx_whisper_transcriber.py`: MLX backend tests with fake module injection.
- Create `backend/tests/test_asr_segmentation.py`: word-based segmentation tests.
- Modify `backend/app/asr/schemas.py`: add `MLX_WHISPER`, MLX config fields, and subtitle segmentation config.
- Modify `backend/app/asr/factory.py`: populate new config fields and construct `MlxWhisperTranscriber`.
- Modify `backend/app/asr/output.py`: use shared segmentation settings when writing transcript outputs.
- Modify `backend/app/asr/faster_whisper.py`: pass segmentation settings to output writing.
- Modify `backend/app/asr/whisper_cpp.py`: pass segmentation settings to output writing.
- Modify `backend/app/core/config.py`: add MLX and subtitle segmentation environment settings; switch default backend.
- Modify `backend/app/api/settings.py`: expose active ASR backend, MLX model, and segmentation settings.
- Modify `backend/tests/test_asr_factory.py`: update default backend and MLX construction expectations.
- Modify `backend/tests/test_faster_whisper_transcriber.py`: update output writer expectations for word-based segmentation.
- Modify `backend/tests/test_job_runner.py`: keep fake transcriber aligned with new output writer signature.
- Modify `pyproject.toml`: replace or supplement ASR dependency with `mlx-whisper`.
- Modify `frontend/src/api/client.ts`: type new ASR settings.
- Modify `frontend/src/components/JobWorkbench.tsx`: show active backend/model and hide whisper.cpp timestamp controls unless active.
- Modify `frontend/src/__tests__/App.test.tsx`: assert MLX settings render and whisper timestamp controls are hidden by default.
- Modify `README.md`: document MLX setup and legacy fallback.

## Task 1: Backend ASR Config And Factory

**Files:**
- Modify: `backend/app/asr/schemas.py`
- Modify: `backend/app/asr/factory.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_asr_factory.py`

- [ ] **Step 1: Write failing factory tests**

Replace `backend/tests/test_asr_factory.py` with:

```python
from app.asr.factory import asr_config_from_settings, build_transcriber
from app.asr.schemas import AsrBackend
from app.asr.whisper_cpp import WhisperCppTranscriber
from app.core.config import Settings


def test_build_transcriber_selects_mlx_whisper_by_default() -> None:
    config = asr_config_from_settings(Settings())
    transcriber = build_transcriber(config)

    assert config.backend == AsrBackend.MLX_WHISPER
    assert transcriber.__class__.__name__ == "MlxWhisperTranscriber"
    assert config.mlx_whisper_model == "mlx-community/whisper-large-v3-mlx"
    assert config.segmentation.max_chars == 42


def test_build_transcriber_selects_faster_whisper_when_configured() -> None:
    config = asr_config_from_settings(Settings(asr_backend=AsrBackend.FASTER_WHISPER))
    transcriber = build_transcriber(config)

    assert transcriber.__class__.__name__ == "FasterWhisperTranscriber"


def test_build_transcriber_selects_whisper_cpp_when_configured() -> None:
    config = asr_config_from_settings(Settings(asr_backend=AsrBackend.WHISPER_CPP))
    transcriber = build_transcriber(config)

    assert isinstance(transcriber, WhisperCppTranscriber)
```

- [ ] **Step 2: Run the focused test and verify failure**

Run:

```bash
python -m pytest backend/tests/test_asr_factory.py -v
```

Expected: FAIL because `AsrBackend.MLX_WHISPER`, MLX settings, and `MlxWhisperTranscriber` do not exist.

- [ ] **Step 3: Implement schema and config fields**

Update `backend/app/asr/schemas.py` so the relevant definitions include:

```python
class AsrBackend(StrEnum):
    WHISPER_CPP = "whisper_cpp"
    FASTER_WHISPER = "faster_whisper"
    MLX_WHISPER = "mlx_whisper"


class SubtitleSegmentationConfig(BaseModel):
    max_chars: int = Field(default=42, ge=1)
    max_duration_ms: int = Field(default=6000, ge=1)
    min_duration_ms: int = Field(default=800, ge=0)
    max_word_gap_ms: int = Field(default=800, ge=0)


class AsrConfig(BaseModel):
    backend: AsrBackend = AsrBackend.MLX_WHISPER
    model: str = "large-v3-turbo"
    device: str = "cpu"
    compute_type: str = "int8"
    vad_filter: bool = True
    min_silence_duration_ms: int = Field(default=500, ge=0)
    word_timestamps: bool = True
    beam_size: int = Field(default=1, ge=1)
    cpu_threads: int = Field(default=0, ge=0)
    num_workers: int = Field(default=1, ge=1)
    condition_on_previous_text: bool = False
    model_dir: str = ""
    mlx_whisper_model: str = "mlx-community/whisper-large-v3-mlx"
    mlx_whisper_model_dir: str = ""
    mlx_whisper_word_timestamps: bool = True
    segmentation: SubtitleSegmentationConfig = Field(default_factory=SubtitleSegmentationConfig)
    executable_path: Path = Path()
    model_path: Path = Path()
    whisper_settings: WhisperSettings = Field(default_factory=WhisperSettings)
```

Update `backend/app/core/config.py` so the ASR settings include:

```python
asr_backend: AsrBackend = AsrBackend.MLX_WHISPER
mlx_whisper_model: str = "mlx-community/whisper-large-v3-mlx"
mlx_whisper_model_dir: str = ""
mlx_whisper_word_timestamps: bool = True
asr_max_subtitle_chars: int = 42
asr_max_subtitle_duration_ms: int = 6000
asr_min_subtitle_duration_ms: int = 800
asr_max_word_gap_ms: int = 800
```

- [ ] **Step 4: Implement factory wiring**

Update `backend/app/asr/factory.py`:

```python
from app.asr.mlx_whisper import MlxWhisperTranscriber
from app.asr.schemas import AsrBackend, AsrConfig, SubtitleSegmentationConfig, Transcriber


def asr_config_from_settings(settings: Settings, job_config: JobCreate | None = None) -> AsrConfig:
    whisper_settings = (
        job_config.whisper_settings if job_config is not None else WhisperSettings()
    )
    return AsrConfig(
        backend=settings.asr_backend,
        model=settings.faster_whisper_model,
        device=settings.faster_whisper_device,
        compute_type=settings.faster_whisper_compute_type,
        vad_filter=settings.faster_whisper_vad_filter,
        min_silence_duration_ms=settings.faster_whisper_min_silence_duration_ms,
        word_timestamps=settings.faster_whisper_word_timestamps,
        beam_size=settings.faster_whisper_beam_size,
        cpu_threads=settings.faster_whisper_cpu_threads,
        num_workers=settings.faster_whisper_num_workers,
        condition_on_previous_text=settings.faster_whisper_condition_on_previous_text,
        model_dir=settings.faster_whisper_model_dir,
        mlx_whisper_model=settings.mlx_whisper_model,
        mlx_whisper_model_dir=settings.mlx_whisper_model_dir,
        mlx_whisper_word_timestamps=settings.mlx_whisper_word_timestamps,
        segmentation=SubtitleSegmentationConfig(
            max_chars=settings.asr_max_subtitle_chars,
            max_duration_ms=settings.asr_max_subtitle_duration_ms,
            min_duration_ms=settings.asr_min_subtitle_duration_ms,
            max_word_gap_ms=settings.asr_max_word_gap_ms,
        ),
        executable_path=Path(settings.whisper_executable_path) if settings.whisper_executable_path else Path(),
        model_path=Path(settings.whisper_model_path) if settings.whisper_model_path else Path(),
        whisper_settings=whisper_settings,
    )


def build_transcriber(config: AsrConfig) -> Transcriber:
    if config.backend == AsrBackend.MLX_WHISPER:
        return MlxWhisperTranscriber(config)
    if config.backend == AsrBackend.FASTER_WHISPER:
        return FasterWhisperTranscriber(config)
    return WhisperCppTranscriber(config)
```

Create a temporary minimal `backend/app/asr/mlx_whisper.py`:

```python
from app.asr.schemas import AsrConfig, TranscribeRequest, TranscriptionResult


class MlxWhisperTranscriber:
    def __init__(self, config: AsrConfig) -> None:
        self.config = config

    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult:
        raise NotImplementedError("mlx-whisper transcription is implemented in Task 3")
```

- [ ] **Step 5: Run the focused test and verify pass**

Run:

```bash
python -m pytest backend/tests/test_asr_factory.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/asr/schemas.py backend/app/asr/factory.py backend/app/core/config.py backend/app/asr/mlx_whisper.py backend/tests/test_asr_factory.py
git commit -m "feat: add mlx whisper asr config"
```

## Task 2: Word-Based Subtitle Segmentation

**Files:**
- Create: `backend/app/asr/segmentation.py`
- Modify: `backend/app/asr/output.py`
- Modify: `backend/app/asr/faster_whisper.py`
- Modify: `backend/app/asr/whisper_cpp.py`
- Test: `backend/tests/test_asr_segmentation.py`
- Test: `backend/tests/test_faster_whisper_transcriber.py`

- [ ] **Step 1: Write segmentation tests**

Create `backend/tests/test_asr_segmentation.py`:

```python
from app.asr.schemas import (
    SubtitleSegmentationConfig,
    TranscriptionResult,
    TranscriptionSegment,
    WordTimestamp,
)
from app.asr.segmentation import transcription_to_subtitle_segments


def make_result(words: list[WordTimestamp]) -> TranscriptionResult:
    return TranscriptionResult(
        language="en",
        duration=10.0,
        segments=[
            TranscriptionSegment(id=0, start=words[0].start, end=words[-1].end, text=" ".join(word.word for word in words), words=words)
        ],
        text=" ".join(word.word for word in words),
    )


def test_segments_from_word_timestamps_preserve_word_bounds() -> None:
    result = make_result(
        [
            WordTimestamp(word="Hello", start=0.32, end=0.70),
            WordTimestamp(word="world.", start=0.72, end=1.05),
        ]
    )

    segments = transcription_to_subtitle_segments(result, SubtitleSegmentationConfig())

    assert len(segments) == 1
    assert segments[0].start_ms == 320
    assert segments[0].end_ms == 1050
    assert segments[0].text == "Hello world."


def test_segments_split_on_large_word_gap() -> None:
    result = make_result(
        [
            WordTimestamp(word="First", start=0.0, end=0.4),
            WordTimestamp(word="line.", start=0.5, end=0.8),
            WordTimestamp(word="Second", start=2.0, end=2.4),
            WordTimestamp(word="line.", start=2.5, end=3.0),
        ]
    )

    segments = transcription_to_subtitle_segments(
        result,
        SubtitleSegmentationConfig(max_word_gap_ms=800),
    )

    assert [segment.text for segment in segments] == ["First line.", "Second line."]


def test_segments_split_before_exceeding_max_chars() -> None:
    result = make_result(
        [
            WordTimestamp(word="One", start=0.0, end=0.2),
            WordTimestamp(word="two", start=0.3, end=0.5),
            WordTimestamp(word="three", start=0.6, end=0.8),
        ]
    )

    segments = transcription_to_subtitle_segments(
        result,
        SubtitleSegmentationConfig(max_chars=7),
    )

    assert [segment.text for segment in segments] == ["One two", "three"]


def test_segments_fall_back_to_model_segments_without_words() -> None:
    result = TranscriptionResult(
        language="en",
        duration=1.25,
        segments=[TranscriptionSegment(id=0, start=0.32, end=1.25, text="Fallback")],
        text="Fallback",
    )

    segments = transcription_to_subtitle_segments(result, SubtitleSegmentationConfig())

    assert segments[0].start_ms == 320
    assert segments[0].end_ms == 1250
    assert segments[0].text == "Fallback"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
python -m pytest backend/tests/test_asr_segmentation.py -v
```

Expected: FAIL because `app.asr.segmentation` does not exist.

- [ ] **Step 3: Implement segmentation module**

Create `backend/app/asr/segmentation.py`:

```python
from app.asr.schemas import SubtitleSegmentationConfig, TranscriptionResult, WordTimestamp
from app.subtitles.schemas import SubtitleSegment


SENTENCE_ENDINGS = (".", "!", "?", "。", "！", "？")
PHRASE_ENDINGS = (",", ";", ":", "，", "；", "：", "、")


def seconds_to_ms(value: float) -> int:
    return int(round(value * 1000))


def clean_words(result: TranscriptionResult) -> list[WordTimestamp]:
    words: list[WordTimestamp] = []
    for segment in result.segments:
        for word in segment.words:
            text = word.word.strip()
            if not text or word.end <= word.start:
                continue
            words.append(word.model_copy(update={"word": text}))
    return words


def join_words(words: list[WordTimestamp]) -> str:
    return " ".join(word.word.strip() for word in words if word.word.strip()).strip()


def should_break(
    current: list[WordTimestamp],
    next_word: WordTimestamp,
    config: SubtitleSegmentationConfig,
) -> bool:
    if not current:
        return False
    current_text = join_words(current)
    next_text = f"{current_text} {next_word.word.strip()}".strip()
    duration_ms = seconds_to_ms(next_word.end - current[0].start)
    gap_ms = seconds_to_ms(next_word.start - current[-1].end)
    if gap_ms > config.max_word_gap_ms:
        return True
    if len(next_text) > config.max_chars:
        return True
    if duration_ms > config.max_duration_ms:
        return True
    if current[-1].word.strip().endswith(SENTENCE_ENDINGS):
        current_duration_ms = seconds_to_ms(current[-1].end - current[0].start)
        return current_duration_ms >= config.min_duration_ms
    if current[-1].word.strip().endswith(PHRASE_ENDINGS):
        return len(current_text) >= int(config.max_chars * 0.75)
    return False


def segments_from_words(
    words: list[WordTimestamp],
    config: SubtitleSegmentationConfig,
) -> list[SubtitleSegment]:
    groups: list[list[WordTimestamp]] = []
    current: list[WordTimestamp] = []
    for word in words:
        if should_break(current, word, config):
            groups.append(current)
            current = []
        current.append(word)
    if current:
        groups.append(current)

    return [
        SubtitleSegment(
            index=index,
            start_ms=seconds_to_ms(group[0].start),
            end_ms=seconds_to_ms(group[-1].end),
            text=join_words(group),
        )
        for index, group in enumerate(groups, start=1)
        if join_words(group)
    ]


def segments_from_model_segments(result: TranscriptionResult) -> list[SubtitleSegment]:
    subtitle_segments: list[SubtitleSegment] = []
    for index, segment in enumerate(result.segments, start=1):
        text = segment.text.strip()
        if not text:
            continue
        subtitle_segments.append(
            SubtitleSegment(
                index=index,
                start_ms=seconds_to_ms(segment.start),
                end_ms=seconds_to_ms(segment.end),
                text=text,
            )
        )
    return subtitle_segments


def transcription_to_subtitle_segments(
    result: TranscriptionResult,
    config: SubtitleSegmentationConfig,
) -> list[SubtitleSegment]:
    words = clean_words(result)
    if words:
        return segments_from_words(words, config)
    return segments_from_model_segments(result)
```

- [ ] **Step 4: Wire output writer to segmentation**

Update `backend/app/asr/output.py`:

```python
import json
from pathlib import Path

from app.asr.schemas import SubtitleSegmentationConfig, TranscriptionResult
from app.asr.segmentation import seconds_to_ms, transcription_to_subtitle_segments
from app.subtitles.srt import format_markdown, format_srt, format_txt


def write_transcription_outputs(
    output_prefix: Path,
    result: TranscriptionResult,
    segmentation: SubtitleSegmentationConfig | None = None,
) -> Path:
    segments = transcription_to_subtitle_segments(
        result,
        segmentation or SubtitleSegmentationConfig(),
    )
    if not segments:
        raise RuntimeError("transcription produced no subtitle segments")

    srt_path = output_prefix.with_suffix(".srt")
    txt_path = output_prefix.with_suffix(".txt")
    md_path = output_prefix.with_suffix(".md")
    json_path = output_prefix.with_suffix(".json")

    srt_path.write_text(format_srt(segments), encoding="utf-8")
    txt_path.write_text(format_txt(segments), encoding="utf-8")
    md_path.write_text(format_markdown(segments), encoding="utf-8")
    json_path.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return srt_path
```

Update `backend/app/asr/faster_whisper.py` and `backend/app/asr/whisper_cpp.py` calls:

```python
write_transcription_outputs(request.output_prefix, result, self.config.segmentation)
```

- [ ] **Step 5: Update existing output tests**

In `backend/tests/test_faster_whisper_transcriber.py`, update imports:

```python
from app.asr.output import seconds_to_ms, write_transcription_outputs
from app.asr.segmentation import transcription_to_subtitle_segments
from app.asr.schemas import AsrConfig, SubtitleSegmentationConfig, TranscribeRequest, TranscriptionResult, TranscriptionSegment, WordTimestamp
```

Update calls to:

```python
segments = transcription_to_subtitle_segments(result, SubtitleSegmentationConfig())
```

Keep assertions that check millisecond preservation.

- [ ] **Step 6: Run segmentation and faster-whisper tests**

Run:

```bash
python -m pytest backend/tests/test_asr_segmentation.py backend/tests/test_faster_whisper_transcriber.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/asr/segmentation.py backend/app/asr/output.py backend/app/asr/faster_whisper.py backend/app/asr/whisper_cpp.py backend/tests/test_asr_segmentation.py backend/tests/test_faster_whisper_transcriber.py
git commit -m "feat: segment transcripts from word timestamps"
```

## Task 3: MLX Whisper Transcriber

**Files:**
- Modify: `backend/app/asr/mlx_whisper.py`
- Test: `backend/tests/test_mlx_whisper_transcriber.py`

- [ ] **Step 1: Write MLX transcriber tests**

Create `backend/tests/test_mlx_whisper_transcriber.py`:

```python
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.asr.mlx_whisper import MlxWhisperTranscriber
from app.asr.schemas import AsrConfig, TranscribeRequest
from app.core.constants import SourceLanguage


def test_mlx_whisper_transcriber_writes_outputs(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    calls: list[dict] = []

    def fake_transcribe(path: str, **kwargs):
        calls.append({"path": path, **kwargs})
        return {
            "language": "ja",
            "text": "こんにちは 世界。",
            "segments": [
                {
                    "id": 0,
                    "start": 0.32,
                    "end": 1.20,
                    "text": "こんにちは 世界。",
                    "words": [
                        {"word": "こんにちは", "start": 0.32, "end": 0.80, "probability": 0.95},
                        {"word": "世界。", "start": 0.82, "end": 1.20, "probability": 0.93},
                    ],
                }
            ],
        }

    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=fake_transcribe),
    )

    transcriber = MlxWhisperTranscriber(AsrConfig())
    result = transcriber.transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=tmp_path / "transcript",
            source_language=SourceLanguage.JAPANESE,
        )
    )

    assert calls[0]["path"] == str(audio_path)
    assert calls[0]["path_or_hf_repo"] == "mlx-community/whisper-large-v3-mlx"
    assert calls[0]["language"] == "ja"
    assert calls[0]["word_timestamps"] is True
    assert result.language == "ja"
    assert result.segments[0].words[0].start == 0.32
    assert "00:00:00,320 --> 00:00:01,200" in (tmp_path / "transcript.srt").read_text(encoding="utf-8")


def test_mlx_whisper_transcriber_omits_auto_language(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    calls: list[dict] = []

    def fake_transcribe(path: str, **kwargs):
        calls.append(kwargs)
        return {
            "language": "en",
            "text": "Hello",
            "segments": [{"start": 0.0, "end": 0.5, "text": "Hello"}],
        }

    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=fake_transcribe),
    )

    MlxWhisperTranscriber(AsrConfig()).transcribe(
        TranscribeRequest(
            audio_path=audio_path,
            job_dir=tmp_path,
            output_prefix=tmp_path / "transcript",
            source_language=SourceLanguage.AUTO,
        )
    )

    assert "language" not in calls[0]


def test_mlx_whisper_transcriber_raises_readable_error_when_dependency_missing(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")

    def missing_module():
        raise ImportError("No module named mlx_whisper")

    monkeypatch.setattr("app.asr.mlx_whisper.import_mlx_whisper", missing_module)

    with pytest.raises(RuntimeError, match="mlx-whisper is not installed"):
        MlxWhisperTranscriber(AsrConfig()).transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )


def test_mlx_whisper_transcriber_raises_when_segments_empty(tmp_path: Path, monkeypatch) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_text("audio", encoding="utf-8")
    monkeypatch.setattr(
        "app.asr.mlx_whisper.import_mlx_whisper",
        lambda: SimpleNamespace(transcribe=lambda path, **kwargs: {"segments": [], "text": ""}),
    )

    with pytest.raises(RuntimeError, match="returned no speech segments"):
        MlxWhisperTranscriber(AsrConfig()).transcribe(
            TranscribeRequest(
                audio_path=audio_path,
                job_dir=tmp_path,
                output_prefix=tmp_path / "transcript",
            )
        )
```

- [ ] **Step 2: Run MLX tests and verify failure**

Run:

```bash
python -m pytest backend/tests/test_mlx_whisper_transcriber.py -v
```

Expected: FAIL because `MlxWhisperTranscriber.transcribe` is still a stub.

- [ ] **Step 3: Implement MLX transcriber**

Replace `backend/app/asr/mlx_whisper.py` with:

```python
from pathlib import Path
from types import ModuleType
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


def import_mlx_whisper() -> ModuleType:
    try:
        import mlx_whisper
    except ImportError as exc:
        raise RuntimeError("mlx-whisper is not installed. Run: pip install mlx-whisper") from exc
    return mlx_whisper


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
            normalized.append(
                WordTimestamp(
                    word=text,
                    start=float(start),
                    end=float(end),
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
        mlx_whisper = import_mlx_whisper()
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
        write_transcription_outputs(request.output_prefix, result, self.config.segmentation)
        return result
```

- [ ] **Step 4: Run MLX tests and verify pass**

Run:

```bash
python -m pytest backend/tests/test_mlx_whisper_transcriber.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/asr/mlx_whisper.py backend/tests/test_mlx_whisper_transcriber.py
git commit -m "feat: add mlx whisper transcriber"
```

## Task 4: Settings API And Frontend Surface

**Files:**
- Modify: `backend/app/api/settings.py`
- Modify: `backend/tests/test_settings.py`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/JobWorkbench.tsx`
- Modify: `frontend/src/__tests__/App.test.tsx`

- [ ] **Step 1: Write or update settings tests**

Update `backend/tests/test_settings.py` to assert:

```python
def test_settings_include_mlx_asr_fields(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("TM_SQLITE_PATH", str(tmp_path / "app.db"))
    monkeypatch.setenv("TM_ASR_BACKEND", "mlx_whisper")
    monkeypatch.setenv("TM_MLX_WHISPER_MODEL", "mlx-community/whisper-large-v3-mlx")

    response = client.get("/api/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["asr_backend"] == "mlx_whisper"
    assert payload["mlx_whisper_model"] == "mlx-community/whisper-large-v3-mlx"
    assert payload["asr_max_subtitle_chars"] == 42
```

- [ ] **Step 2: Run backend settings test and verify failure**

Run:

```bash
python -m pytest backend/tests/test_settings.py -v
```

Expected: FAIL until `/api/settings` exposes the new fields.

- [ ] **Step 3: Expose ASR settings**

Update `backend/app/api/settings.py` response to include:

```python
"asr_backend": settings.asr_backend.value,
"mlx_whisper_model": settings.mlx_whisper_model,
"mlx_whisper_model_dir": settings.mlx_whisper_model_dir,
"mlx_whisper_word_timestamps": settings.mlx_whisper_word_timestamps,
"asr_max_subtitle_chars": settings.asr_max_subtitle_chars,
"asr_max_subtitle_duration_ms": settings.asr_max_subtitle_duration_ms,
"asr_min_subtitle_duration_ms": settings.asr_min_subtitle_duration_ms,
"asr_max_word_gap_ms": settings.asr_max_word_gap_ms,
```

- [ ] **Step 4: Update frontend settings type**

Update `frontend/src/api/client.ts`:

```ts
export interface AppSettings {
  asr_backend: string;
  mlx_whisper_model: string;
  mlx_whisper_model_dir: string;
  mlx_whisper_word_timestamps: boolean;
  asr_max_subtitle_chars: number;
  asr_max_subtitle_duration_ms: number;
  asr_min_subtitle_duration_ms: number;
  asr_max_word_gap_ms: number;
  whisper_executable_path: string;
  whisper_model_path: string;
  whisper_timestamp_precision: string;
  whisper_dtw_preset: string;
  provider_base_url: string;
  provider_model: string;
}
```

- [ ] **Step 5: Update workbench UI**

Add state in `frontend/src/components/JobWorkbench.tsx`:

```ts
const [asrBackend, setAsrBackend] = useState("");
const [mlxWhisperModel, setMlxWhisperModel] = useState("");
```

Set it from settings:

```ts
setAsrBackend(settings.asr_backend);
setMlxWhisperModel(settings.mlx_whisper_model);
```

Render a compact ASR fieldset above timestamp controls:

```tsx
{file && !isSrtFile(file) ? (
  <fieldset>
    <legend>Transcription backend</legend>
    <p className="field-hint">
      {asrBackend === "mlx_whisper"
        ? `MLX Whisper: ${mlxWhisperModel || "default model"}`
        : asrBackend === "whisper_cpp"
          ? "whisper.cpp"
          : asrBackend
            ? `ASR backend: ${asrBackend}`
            : "ASR backend"}
    </p>
  </fieldset>
) : null}
```

Wrap the existing timestamp fieldset so it only renders for `whisper_cpp`. The
fieldset body remains the current `Timestamp precision`, hint, and conditional
`DTW preset` controls from `JobWorkbench.tsx`:

```tsx
{file && !isSrtFile(file) && asrBackend === "whisper_cpp" ? (
  <fieldset>{/* current Transcription timestamps controls */}</fieldset>
) : null}
```

- [ ] **Step 6: Update frontend test mock and assertions**

In `frontend/src/__tests__/App.test.tsx`, make `/api/settings` return:

```ts
asr_backend: "mlx_whisper",
mlx_whisper_model: "mlx-community/whisper-large-v3-mlx",
mlx_whisper_model_dir: "",
mlx_whisper_word_timestamps: true,
asr_max_subtitle_chars: 42,
asr_max_subtitle_duration_ms: 6000,
asr_min_subtitle_duration_ms: 800,
asr_max_word_gap_ms: 800,
```

Add a test that uploads a fake video file and asserts:

```ts
expect(await screen.findByText(/MLX Whisper:/)).toBeInTheDocument();
expect(screen.queryByLabelText("Timestamp precision")).not.toBeInTheDocument();
```

- [ ] **Step 7: Run backend and frontend focused tests**

Run:

```bash
python -m pytest backend/tests/test_settings.py -v
cd frontend && npm test -- App.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/settings.py backend/tests/test_settings.py frontend/src/api/client.ts frontend/src/components/JobWorkbench.tsx frontend/src/__tests__/App.test.tsx
git commit -m "feat: show active asr backend settings"
```

## Task 5: Dependency And Documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Update dependency**

In `pyproject.toml`, update dependencies to include:

```toml
"mlx-whisper>=0.4.0",
```

Keep the existing `faster-whisper>=1.1.0` dependency so the fallback backend
continues to work after the default changes to MLX.

- [ ] **Step 2: Update README setup**

In `README.md`, update ASR prerequisites and `.env` example:

```bash
TM_ASR_BACKEND=mlx_whisper
TM_MLX_WHISPER_MODEL=mlx-community/whisper-large-v3-mlx
TM_MLX_WHISPER_MODEL_DIR=
TM_MLX_WHISPER_WORD_TIMESTAMPS=true

TM_ASR_MAX_SUBTITLE_CHARS=42
TM_ASR_MAX_SUBTITLE_DURATION_MS=6000
TM_ASR_MIN_SUBTITLE_DURATION_MS=800
TM_ASR_MAX_WORD_GAP_MS=800
```

Add fallback guidance:

```bash
TM_ASR_BACKEND=whisper_cpp
TM_WHISPER_EXECUTABLE_PATH=/absolute/path/to/whisper-cli
TM_WHISPER_MODEL_PATH=/absolute/path/to/ggml-model.bin
```

- [ ] **Step 3: Run metadata checks**

Run:

```bash
python -m pytest backend/tests/test_asr_factory.py backend/tests/test_mlx_whisper_transcriber.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml README.md
git commit -m "docs: document mlx whisper backend"
```

## Task 6: Full Verification

**Files:**
- No new files.

- [ ] **Step 1: Run backend tests**

Run:

```bash
python -m pytest
```

Expected: all backend tests pass.

- [ ] **Step 2: Run backend lint**

Run:

```bash
python -m ruff check backend
```

Expected: no lint errors.

- [ ] **Step 3: Run frontend tests**

Run:

```bash
cd frontend && npm test
```

Expected: all frontend tests pass.

- [ ] **Step 4: Run frontend build**

Run:

```bash
cd frontend && npm run build
```

Expected: production build succeeds.

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short --branch
```

Expected: branch is ahead by the new commits; unrelated pre-existing local edits are not reverted.
