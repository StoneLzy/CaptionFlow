import shutil
import subprocess
from pathlib import Path

from app.media.binaries import ensure_ffmpeg_available
from app.whisper.audio import probe_stream_types


def find_track_file(job_dir: Path, stem: str) -> Path | None:
    for path in sorted(job_dir.glob(f"{stem}.*")):
        if path.is_file() and path.suffix.lower() not in {".srt", ".txt", ".md", ".json", ".wav"}:
            return path
    return None


def mux_video_audio_stream_copy(
    video_path: Path,
    audio_path: Path,
    output_path: Path,
    *,
    use_shortest: bool = False,
) -> Path:
    ffmpeg = ensure_ffmpeg_available()
    if "video" not in probe_stream_types(video_path):
        raise RuntimeError(f"no video stream found in {video_path.name}")
    if "audio" not in probe_stream_types(audio_path):
        raise RuntimeError(f"no audio stream found in {audio_path.name}")

    command = [
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-i",
        str(audio_path),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c",
        "copy",
    ]
    if use_shortest:
        command.append("-shortest")
    command.append(str(output_path))

    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0 or not output_path.exists():
        details = (result.stderr or result.stdout or "ffmpeg mux failed").strip()
        raise RuntimeError(f"track mux failed: {details}")
    return output_path


def copy_as_input_mp4(source_path: Path, job_dir: Path) -> Path:
    target = job_dir / "input.mp4"
    shutil.copy2(source_path, target)
    return target
