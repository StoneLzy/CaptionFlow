from enum import StrEnum

from pydantic import BaseModel, Field


class StageName(StrEnum):
    UPLOAD = "upload"
    DOWNLOAD = "download"
    TRACK_MUX = "track_mux"
    TRANSCRIPTION = "transcription"
    MERGE = "merge"
    TRANSLATION = "translation"
    EXPORT = "export"


STAGE_ORDER: tuple[StageName, ...] = (
    StageName.UPLOAD,
    StageName.DOWNLOAD,
    StageName.TRACK_MUX,
    StageName.TRANSCRIPTION,
    StageName.MERGE,
    StageName.TRANSLATION,
    StageName.EXPORT,
)


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageProgress(BaseModel):
    name: StageName
    status: StageStatus = StageStatus.PENDING
    detail: str = ""
    percent: int | None = Field(default=None, ge=0, le=100)
    processed: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    elapsed_seconds: float | None = Field(default=None, ge=0)
