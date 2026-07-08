from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field

from app.core.constants import SourceLanguage
from app.whisper.schemas import WhisperSettings


class AsrBackend(StrEnum):
    WHISPER_CPP = "whisper_cpp"
    FASTER_WHISPER = "faster_whisper"
    MLX_WHISPER = "mlx_whisper"
    WHISPERKIT_SERVER = "whisperkit_server"


class WordTimestamp(BaseModel):
    word: str
    start: float
    end: float
    probability: float | None = None


class TranscriptionSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[WordTimestamp] = Field(default_factory=list)


class TranscriptionResult(BaseModel):
    language: str
    duration: float
    segments: list[TranscriptionSegment]
    text: str


class SubtitleSegmentationConfig(BaseModel):
    max_chars: int = Field(default=42, ge=1)
    max_duration_ms: int = Field(default=6000, ge=1)
    min_duration_ms: int = Field(default=800, ge=0)
    max_word_gap_ms: int = Field(default=800, ge=0)


class AsrConfig(BaseModel):
    backend: AsrBackend = AsrBackend.WHISPERKIT_SERVER
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
    whisperkit_executable_path: Path = Path()
    whisperkit_cli_workdir: Path = Path()
    whisperkit_model: str = "large-v3-v20240930_626MB"
    whisperkit_model_path: Path = Path()
    whisperkit_host: str = "127.0.0.1"
    whisperkit_startup_timeout_seconds: float = Field(default=120.0, gt=0)
    whisperkit_request_timeout_seconds: float = Field(default=1800.0, gt=0)
    segmentation: SubtitleSegmentationConfig = Field(default_factory=SubtitleSegmentationConfig)
    executable_path: Path = Path()
    model_path: Path = Path()
    whisper_settings: WhisperSettings = Field(default_factory=WhisperSettings)


class TranscribeRequest(BaseModel):
    audio_path: Path
    job_dir: Path
    output_prefix: Path
    source_language: SourceLanguage = SourceLanguage.AUTO
    whisper_settings: WhisperSettings = Field(default_factory=WhisperSettings)
    output_formats: list[str] = Field(default_factory=lambda: ["srt"])
    pipeline_requires_srt: bool = False


class Transcriber(Protocol):
    def transcribe(self, request: TranscribeRequest) -> TranscriptionResult: ...
