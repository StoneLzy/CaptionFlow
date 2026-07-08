from app.jobs.schemas import MergeSettings
from app.subtitles.schemas import SubtitleSegment

SENTENCE_ENDINGS = (".", "!", "?", "。", "！", "？")


def should_merge(current: SubtitleSegment, nxt: SubtitleSegment, settings: MergeSettings) -> bool:
    if current.duration_ms >= settings.min_duration_ms:
        return False
    if nxt.start_ms - current.end_ms > settings.max_gap_ms:
        return False
    if settings.protect_sentence_endings and current.text.rstrip().endswith(SENTENCE_ENDINGS):
        return False
    combined = f"{current.text} {nxt.text}".strip()
    return len(combined) <= settings.max_chars


def merge_two(left: SubtitleSegment, right: SubtitleSegment) -> SubtitleSegment:
    return SubtitleSegment(
        index=left.index,
        start_ms=left.start_ms,
        end_ms=right.end_ms,
        text=f"{left.text} {right.text}".strip(),
    )


def reindex(segments: list[SubtitleSegment]) -> list[SubtitleSegment]:
    return [
        SubtitleSegment(index=index, start_ms=segment.start_ms, end_ms=segment.end_ms, text=segment.text)
        for index, segment in enumerate(segments, start=1)
    ]


def merge_segments(
    segments: list[SubtitleSegment], settings: MergeSettings
) -> list[SubtitleSegment]:
    if not settings.enabled:
        return reindex(segments)

    output: list[SubtitleSegment] = []
    index = 0
    while index < len(segments):
        current = segments[index]
        while index + 1 < len(segments) and should_merge(current, segments[index + 1], settings):
            current = merge_two(current, segments[index + 1])
            index += 1
        output.append(current)
        index += 1
    return reindex(output)
