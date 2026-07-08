from app.subtitles.schemas import SubtitleSegment


def parse_timestamp(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, milliseconds = rest.split(",")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(milliseconds)
    )


def format_timestamp(ms: int) -> str:
    hours, remainder = divmod(ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"


def parse_srt(content: str) -> list[SubtitleSegment]:
    blocks = [
        block.strip() for block in content.replace("\r\n", "\n").split("\n\n") if block.strip()
    ]
    segments: list[SubtitleSegment] = []
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 3:
            raise ValueError(f"Invalid SRT block: {block}")
        index = int(lines[0].strip())
        start_raw, end_raw = [part.strip() for part in lines[1].split("-->")]
        text = "\n".join(line.strip() for line in lines[2:] if line.strip())
        segments.append(
            SubtitleSegment(
                index=index,
                start_ms=parse_timestamp(start_raw),
                end_ms=parse_timestamp(end_raw),
                text=text,
            )
        )
    return segments


def format_srt(segments: list[SubtitleSegment]) -> str:
    blocks: list[str] = []
    for output_index, segment in enumerate(segments, start=1):
        blocks.append(
            "\n".join(
                [
                    str(output_index),
                    f"{format_timestamp(segment.start_ms)} --> {format_timestamp(segment.end_ms)}",
                    segment.text,
                ]
            )
        )
    return "\n\n".join(blocks) + "\n"


def format_txt(segments: list[SubtitleSegment]) -> str:
    return "".join(segment.text.replace("\n", " ") + "\n" for segment in segments)


def format_markdown(segments: list[SubtitleSegment]) -> str:
    rows = ["| # | Start | End | Text |", "|---:|---|---|---|"]
    for segment in segments:
        text = segment.text.replace("|", "\\|").replace("\n", "<br>")
        rows.append(
            f"| {segment.index} | {format_timestamp(segment.start_ms)} | "
            f"{format_timestamp(segment.end_ms)} | {text} |"
        )
    return "\n".join(rows) + "\n"
