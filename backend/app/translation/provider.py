from typing import Protocol

from pydantic import BaseModel

from app.jobs.schemas import ProviderSettings, TerminologyEntry
from app.subtitles.schemas import SubtitleSegment


class TranslatedSegment(BaseModel):
    id: int
    text: str


class TranslationResult(BaseModel):
    items: list[TranslatedSegment]
    model: str


class TranslationProvider(Protocol):
    async def translate(
        self,
        *,
        segments: list[SubtitleSegment],
        source_language: str,
        target_language: str,
        system_prompt: str,
        terminology: list[TerminologyEntry],
        settings: ProviderSettings,
        context_segments: list[SubtitleSegment] | None = None,
    ) -> TranslationResult:
        raise NotImplementedError
