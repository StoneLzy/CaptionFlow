import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.jobs.schemas import YtdlpFormatPreset, YtdlpSettings
from app.media.mux import find_track_file
from app.whisper.audio import probe_stream_types


@dataclass(frozen=True)
class YtdlpDownloadResult:
    title: str
    merged_by_ytdlp: bool
    primary_path: Path
    video_path: Path | None = None
    audio_path: Path | None = None


def ensure_ytdlp_available(executable: str = "yt-dlp") -> None:
    if shutil.which(executable) is None:
        raise RuntimeError(
            f"{executable} is not installed or not on PATH. Install yt-dlp before downloading URLs."
        )


def build_format_string(settings: YtdlpSettings) -> str:
    preset = settings.preset
    if preset == YtdlpFormatPreset.BEST:
        return "bestvideo*+bestaudio/best"
    if preset == YtdlpFormatPreset.BEST_1080P:
        return "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best[height<=1080]"
    if preset == YtdlpFormatPreset.BEST_720P:
        return "bestvideo[height<=720]+bestaudio/best[height<=720]/best[height<=720]"
    if preset == YtdlpFormatPreset.CUSTOM:
        custom = settings.custom_format.strip()
        if not custom:
            raise ValueError("custom yt-dlp format is required when preset is custom")
        return custom
    raise ValueError(f"unsupported yt-dlp preset: {preset}")


def _media_candidates(job_dir: Path) -> list[Path]:
    ignored_suffixes = {".srt", ".txt", ".md", ".json", ".wav", ".url", ".log", ".part"}
    candidates: list[Path] = []
    for path in sorted(job_dir.iterdir()):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        if path.suffix.lower() in ignored_suffixes:
            continue
        if path.name in {"source.url", "ytdlp.log"}:
            continue
        candidates.append(path)
    return candidates


def _classify_media_paths(paths: list[Path]) -> tuple[Path | None, Path | None, Path | None]:
    video_paths: list[Path] = []
    audio_paths: list[Path] = []
    av_paths: list[Path] = []

    for path in paths:
        streams = probe_stream_types(path)
        has_video = "video" in streams
        has_audio = "audio" in streams
        if has_video and has_audio:
            av_paths.append(path)
        elif has_video:
            video_paths.append(path)
        elif has_audio:
            audio_paths.append(path)

    if av_paths:
        return av_paths[0], None, None
    if video_paths and audio_paths:
        return None, video_paths[0], audio_paths[0]
    if len(paths) == 1:
        return paths[0], None, None
    return None, None, None


def _read_download_title(job_dir: Path) -> str:
    for path in sorted(job_dir.glob("*.info.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        title = str(payload.get("title") or "").strip()
        if title:
            return title
    return ""


def normalize_download_files(job_dir: Path) -> YtdlpDownloadResult:
    candidates = _media_candidates(job_dir)
    if not candidates:
        log_path = job_dir / "ytdlp.log"
        log_excerpt = log_path.read_text(encoding="utf-8")[-800:].strip() if log_path.exists() else ""
        detail = "yt-dlp finished without producing a media file"
        if log_excerpt:
            detail = f"{detail}. Log excerpt: {log_excerpt}"
        raise RuntimeError(detail)

    merged_path, video_path, audio_path = _classify_media_paths(candidates)
    if merged_path is not None:
        input_mp4 = job_dir / "input.mp4"
        if merged_path.suffix.lower() == ".mp4":
            if merged_path != input_mp4:
                if input_mp4.exists():
                    input_mp4.unlink()
                merged_path.rename(input_mp4)
        else:
            target = job_dir / f"input{merged_path.suffix or '.mp4'}"
            if merged_path != target:
                if target.exists():
                    target.unlink()
                merged_path.rename(target)
            if not input_mp4.exists():
                shutil.copy2(target, input_mp4)
        if not input_mp4.exists():
            raise RuntimeError("yt-dlp merged file could not be normalized to input.mp4")
        return YtdlpDownloadResult(
            title=input_mp4.name,
            merged_by_ytdlp=True,
            primary_path=input_mp4,
        )

    if video_path is None or audio_path is None:
        raise RuntimeError(
            "yt-dlp output could not be classified as merged or separate audio/video tracks"
        )

    video_target = job_dir / f"input_video{video_path.suffix or '.mp4'}"
    audio_target = job_dir / f"input_audio{audio_path.suffix or '.m4a'}"
    if video_path != video_target:
        if video_target.exists():
            video_target.unlink()
        video_path.rename(video_target)
    if audio_path != audio_target:
        if audio_target.exists():
            audio_target.unlink()
        audio_path.rename(audio_target)

    return YtdlpDownloadResult(
        title=video_target.name,
        merged_by_ytdlp=False,
        primary_path=video_target,
        video_path=video_target,
        audio_path=audio_target,
    )


def download_media(
    url: str,
    output_dir: Path,
    *,
    settings: YtdlpSettings,
    executable: str = "yt-dlp",
    cookies_file: str = "",
) -> YtdlpDownloadResult:
    ensure_ytdlp_available(executable)
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    format_string = build_format_string(settings)
    log_path = output_dir / "ytdlp.log"

    command = [
        executable,
        "--no-playlist",
        "--restrict-filenames",
        "-f",
        format_string,
        "--merge-output-format",
        "mp4",
        "--write-info-json",
        "-o",
        "ytdlp.%(ext)s",
        url,
    ]
    if cookies_file.strip():
        command[1:1] = ["--cookies", cookies_file.strip()]

    result = subprocess.run(
        command,
        cwd=str(output_dir),
        text=True,
        capture_output=True,
        check=False,
    )
    log_path.write_text((result.stderr or result.stdout or "").strip(), encoding="utf-8")
    if result.returncode != 0:
        details = (result.stderr or result.stdout or "yt-dlp download failed").strip()
        if not output_dir.exists():
            raise RuntimeError(
                "yt-dlp download failed because the job directory was removed during download"
            )
        raise RuntimeError(f"yt-dlp download failed: {details}")

    normalized = normalize_download_files(output_dir)
    title = _read_download_title(output_dir) or normalized.title
    return YtdlpDownloadResult(
        title=title or normalized.title,
        merged_by_ytdlp=normalized.merged_by_ytdlp,
        primary_path=normalized.primary_path,
        video_path=normalized.video_path,
        audio_path=normalized.audio_path,
    )


def has_separate_tracks(job_dir: Path) -> bool:
    return find_track_file(job_dir, "input_video") is not None and find_track_file(job_dir, "input_audio") is not None
