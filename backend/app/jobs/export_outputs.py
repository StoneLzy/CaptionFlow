from pathlib import Path

from app.jobs.schemas import JobCreate, OutputFormat


def wants_format(config: JobCreate, fmt: OutputFormat) -> bool:
    return fmt in config.output_formats


def collect_transcript_outputs(job_dir: Path, config: JobCreate) -> dict[str, str]:
    mapping = {
        OutputFormat.SRT: ("transcript.srt", "transcript_srt"),
        OutputFormat.TXT: ("transcript.txt", "transcript_txt"),
        OutputFormat.MD: ("transcript.md", "transcript_md"),
        OutputFormat.JSON: ("transcript.json", "transcript_json"),
    }
    outputs: dict[str, str] = {}
    for fmt, (filename, key) in mapping.items():
        if not wants_format(config, fmt):
            continue
        path = job_dir / filename
        if path.exists():
            outputs[key] = str(path)
    return outputs
