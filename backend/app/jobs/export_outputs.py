import shutil
from pathlib import Path

from app.jobs.schemas import JobCreate, OutputFormat


def wants_format(config: JobCreate, fmt: OutputFormat) -> bool:
    return fmt in config.output_formats


FINAL_OUTPUT_KEYS = {
    "transcript_srt",
    "transcript_txt",
    "transcript_md",
    "transcript_json",
    "merged_srt",
    "translation_srt",
    "bilingual_txt",
    "bilingual_md",
}


def resolve_output_directory(config: JobCreate, fallback_job_dir: Path) -> Path:
    raw = config.output_directory.strip()
    if not raw:
        return fallback_job_dir
    return Path(raw).expanduser().resolve()


def export_final_outputs(
    *,
    outputs: dict[str, str],
    config: JobCreate,
    job_dir: Path,
) -> dict[str, str]:
    output_dir = resolve_output_directory(config, job_dir)
    if output_dir == job_dir.resolve():
        return outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise NotADirectoryError(str(output_dir))

    exported = dict(outputs)
    for key, path_str in outputs.items():
        if key not in FINAL_OUTPUT_KEYS:
            continue
        source = Path(path_str)
        if not source.is_file():
            continue
        target = output_dir / source.name
        if source.resolve() != target.resolve():
            shutil.copy2(source, target)
        exported[key] = str(target)
    return exported


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
