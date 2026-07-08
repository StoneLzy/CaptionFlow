#!/usr/bin/env python3
"""Run repeated WhisperKit jobs and check parent RSS plus child cleanup."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.asr.factory import asr_config_from_settings, build_transcriber
from app.asr.schemas import TranscribeRequest
from app.core.config import AsrBackend, Settings
from app.core.constants import SourceLanguage


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audio",
        type=Path,
        default=ROOT / "data" / "smoke-whisperkit.wav",
        help="Short audio file to transcribe repeatedly.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=3,
        help="Number of sequential WhisperKit jobs to run.",
    )
    parser.add_argument(
        "--source-language",
        default=SourceLanguage.JAPANESE.value,
        choices=[language.value for language in SourceLanguage],
        help="Source language sent to the ASR backend.",
    )
    parser.add_argument(
        "--max-parent-rss-growth-mb",
        type=float,
        default=500.0,
        help="Fail when this Python process RSS grows more than the limit.",
    )
    parser.add_argument(
        "--keep-output",
        action="store_true",
        help="Keep temporary transcript output directories.",
    )
    return parser.parse_args()


def current_rss_mb(pid: int | None = None) -> float:
    target_pid = os.getpid() if pid is None else pid
    result = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(target_pid)],
        check=True,
        capture_output=True,
        text=True,
    )
    rss_kb = int(result.stdout.strip())
    return rss_kb / 1024


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def source_language(value: str) -> SourceLanguage:
    return SourceLanguage(value)


def main() -> int:
    args = parse_args()
    audio = args.audio.expanduser().resolve()
    if not audio.exists():
        print(f"Missing audio file: {audio}", file=sys.stderr)
        return 1
    if args.iterations < 1:
        print("--iterations must be at least 1", file=sys.stderr)
        return 1

    settings = Settings()
    if settings.asr_backend != AsrBackend.WHISPERKIT_SERVER:
        print(
            "Set TM_ASR_BACKEND=whisperkit_server before running this check.",
            file=sys.stderr,
        )
        return 1

    config = asr_config_from_settings(settings)
    transcriber = build_transcriber(config)
    original_start_server = transcriber.start_server
    child_pids: list[int] = []

    def tracked_start_server(port: int):
        process = original_start_server(port)
        child_pids.append(process.pid)
        return process

    transcriber.start_server = tracked_start_server

    baseline_rss = current_rss_mb()
    max_rss = baseline_rss
    language = source_language(args.source_language)
    output_root = Path(tempfile.mkdtemp(prefix="whisperkit-memory-"))

    print(f"audio={audio}")
    print(f"output={output_root}")
    print(f"baseline_parent_rss_mb={baseline_rss:.1f}")
    print("iteration child_pid elapsed_s parent_rss_mb segments text_preview")

    try:
        for index in range(1, args.iterations + 1):
            child_pids.clear()
            job_dir = output_root / f"job-{index}"
            job_dir.mkdir(parents=True, exist_ok=True)
            start = time.time()
            result = transcriber.transcribe(
                TranscribeRequest(
                    audio_path=audio,
                    job_dir=job_dir,
                    output_prefix=job_dir / "transcript",
                    source_language=language,
                )
            )
            elapsed = time.time() - start
            time.sleep(1.0)

            parent_rss = current_rss_mb()
            max_rss = max(max_rss, parent_rss)
            child_pid = child_pids[-1] if child_pids else -1
            if child_pid > 0 and process_is_running(child_pid):
                print(f"WhisperKit child process still running: {child_pid}", file=sys.stderr)
                return 1

            preview = result.text.replace("\n", " ")[:80]
            print(
                f"{index} {child_pid} {elapsed:.1f} {parent_rss:.1f} "
                f"{len(result.segments)} {preview}"
            )

        growth = max_rss - baseline_rss
        print(f"max_parent_rss_mb={max_rss:.1f}")
        print(f"parent_rss_growth_mb={growth:.1f}")
        if growth > args.max_parent_rss_growth_mb:
            print(
                "Parent RSS growth exceeded limit: "
                f"{growth:.1f} MB > {args.max_parent_rss_growth_mb:.1f} MB",
                file=sys.stderr,
            )
            return 1
        return 0
    finally:
        if not args.keep_output:
            shutil.rmtree(output_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
