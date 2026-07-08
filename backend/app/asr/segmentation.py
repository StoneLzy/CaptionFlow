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

    subtitle_segments: list[SubtitleSegment] = []
    for index, group in enumerate(groups, start=1):
        text = join_words(group)
        if not text:
            continue
        subtitle_segments.append(
            SubtitleSegment(
                index=index,
                start_ms=seconds_to_ms(group[0].start),
                end_ms=seconds_to_ms(group[-1].end),
                text=text,
            )
        )
    return subtitle_segments


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
