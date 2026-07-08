from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_TARGET_LANGUAGE, SourceLanguage, TargetLanguage
from app.core.progress import StageProgress
from app.whisper.schemas import WhisperSettings


class JobStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(StrEnum):
    SRT = "srt"
    TXT = "txt"
    MD = "md"
    JSON = "json"


class MergeSettings(BaseModel):
    enabled: bool = False
    min_duration_ms: int = Field(default=1200, ge=0)
    max_chars: int = Field(default=80, ge=1)
    max_gap_ms: int = Field(default=800, ge=0)
    protect_sentence_endings: bool = True


class TerminologyEntry(BaseModel):
    source: str
    target: str


class ProviderSettings(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""


class MediaSource(StrEnum):
    UPLOAD = "upload"
    YTDLP = "ytdlp"


class YtdlpFormatPreset(StrEnum):
    BEST = "best"
    BEST_1080P = "best_1080p"
    BEST_720P = "best_720p"
    CUSTOM = "custom"


class YtdlpSettings(BaseModel):
    url: str = ""
    preset: YtdlpFormatPreset = YtdlpFormatPreset.BEST
    custom_format: str = ""
    cookies_file: str = ""


class TranscribeAudioSource(StrEnum):
    EXTERNAL = "external_audio"
    MUXED = "muxed"


class TrackMuxSettings(BaseModel):
    enabled: bool = False
    transcribe_from: TranscribeAudioSource = TranscribeAudioSource.EXTERNAL
    use_shortest: bool = False


class JobCreate(BaseModel):
    job_name: str = ""
    output_directory: str = ""
    media_source: MediaSource = MediaSource.UPLOAD
    ytdlp_settings: YtdlpSettings = Field(default_factory=YtdlpSettings)
    track_mux_settings: TrackMuxSettings = Field(default_factory=TrackMuxSettings)
    source_language: SourceLanguage = SourceLanguage.AUTO
    target_language: TargetLanguage = DEFAULT_TARGET_LANGUAGE
    output_formats: list[OutputFormat] = Field(default_factory=lambda: [OutputFormat.SRT])
    merge_settings: MergeSettings = Field(default_factory=MergeSettings)
    enable_translation: bool = True
    whisper_settings: WhisperSettings = Field(default_factory=WhisperSettings)
    system_prompt: str = ""
    terminology: list[TerminologyEntry] = Field(default_factory=list)
    provider_settings: ProviderSettings = Field(default_factory=ProviderSettings)


class JobSummary(BaseModel):
    id: UUID
    filename: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    output_directory: str = ""
    progress: list[StageProgress]
    error_summary: str | None = None
    outputs: dict[str, str] = Field(default_factory=dict)


class JobDetail(JobSummary):
    config: JobCreate


class JobRename(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
