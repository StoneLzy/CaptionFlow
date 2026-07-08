from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from app.core.constants import SourceLanguage
from app.whisper.dtw import resolve_dtw_preset


class WhisperTimestampPrecision(StrEnum):
    STANDARD = "standard"
    WORD = "word"
    WORD_DTW = "word_dtw"


class WhisperSettings(BaseModel):
    timestamp_precision: WhisperTimestampPrecision = WhisperTimestampPrecision.STANDARD
    dtw_preset: str = ""


class WhisperRequest(BaseModel):
    executable_path: Path
    model_path: Path
    input_path: Path
    output_prefix: Path
    source_language: SourceLanguage = SourceLanguage.AUTO
    timestamp_precision: WhisperTimestampPrecision = WhisperTimestampPrecision.STANDARD
    dtw_preset: str = Field(default="")

    def resolved_dtw_preset(self) -> str:
        return resolve_dtw_preset(self.model_path, self.dtw_preset)
