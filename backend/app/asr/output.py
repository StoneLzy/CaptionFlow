import json
from pathlib import Path

from app.asr.schemas import SubtitleSegmentationConfig, TranscriptionResult
from app.asr.segmentation import transcription_to_subtitle_segments
from app.subtitles.srt import format_markdown, format_srt, format_txt

TRANSCRIPT_SUFFIXES = {
    "srt": ".srt",
    "txt": ".txt",
    "md": ".md",
    "json": ".json",
}


def write_transcription_outputs(
    output_prefix: Path,
    result: TranscriptionResult,
    segmentation: SubtitleSegmentationConfig | None = None,
    *,
    output_formats: list[str] | None = None,
    pipeline_requires_srt: bool = False,
) -> Path:
    segments = transcription_to_subtitle_segments(
        result,
        segmentation or SubtitleSegmentationConfig(),
    )
    if not segments:
        raise RuntimeError("transcription produced no subtitle segments")

    formats = set(output_formats or ["srt"])
    write_srt = "srt" in formats or pipeline_requires_srt

    srt_path = output_prefix.with_suffix(".srt")
    if write_srt:
        srt_path.write_text(format_srt(segments), encoding="utf-8")

    if "txt" in formats:
        output_prefix.with_suffix(".txt").write_text(format_txt(segments), encoding="utf-8")
    if "md" in formats:
        output_prefix.with_suffix(".md").write_text(format_markdown(segments), encoding="utf-8")
    if "json" in formats:
        output_prefix.with_suffix(".json").write_text(
            json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    _cleanup_unselected_transcript_files(
        output_prefix,
        formats=formats,
        keep_srt=write_srt,
    )

    if srt_path.exists():
        return srt_path
    for fmt in ("json", "txt", "md", "srt"):
        if fmt in formats:
            path = output_prefix.with_suffix(TRANSCRIPT_SUFFIXES[fmt])
            if path.exists():
                return path
    raise RuntimeError("transcription produced no requested output files")


def _cleanup_unselected_transcript_files(
    output_prefix: Path,
    *,
    formats: set[str],
    keep_srt: bool,
) -> None:
    for fmt, suffix in TRANSCRIPT_SUFFIXES.items():
        path = output_prefix.with_suffix(suffix)
        if not path.exists():
            continue
        if fmt == "srt" and keep_srt:
            continue
        if fmt in formats:
            continue
        path.unlink()
