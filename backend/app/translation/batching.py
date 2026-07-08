from app.subtitles.schemas import SubtitleSegment
from app.translation.provider import TranslatedSegment, TranslationResult


def chunk_segments(
    segments: list[SubtitleSegment],
    batch_size: int,
) -> list[list[SubtitleSegment]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    if not segments:
        return []
    return [segments[index : index + batch_size] for index in range(0, len(segments), batch_size)]


def merge_translation_results(results: list[TranslationResult]) -> list[TranslatedSegment]:
    items: list[TranslatedSegment] = []
    for result in results:
        items.extend(result.items)
    return items
