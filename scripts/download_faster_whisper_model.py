#!/usr/bin/env python3
"""Download a faster-whisper CTranslate2 model into the project models/ directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_BY_ALIAS = {
    "large-v3-turbo": "Systran/faster-whisper-large-v3-turbo",
    "large-v3": "Systran/faster-whisper-large-v3",
    "medium": "Systran/faster-whisper-medium",
    "small": "Systran/faster-whisper-small",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="large-v3-turbo",
        help="Model alias or Hugging Face repo id (default: large-v3-turbo)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "models",
        help="Directory to store downloaded models",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_id = REPO_BY_ALIAS.get(args.model, args.model)
    folder_name = repo_id.split("/")[-1]
    target = args.output_dir / folder_name
    target.mkdir(parents=True, exist_ok=True)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub is required. Install with: pip install huggingface_hub", file=sys.stderr)
        return 1

    print(f"Downloading {repo_id}")
    print(f"Target: {target}")
    try:
        snapshot_download(repo_id=repo_id, local_dir=str(target))
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        print(
            "\nIf huggingface.co times out, try:\n"
            "  HF_ENDPOINT=https://hf-mirror.com python scripts/download_faster_whisper_model.py\n"
            "or configure a proxy, then rerun this script.",
            file=sys.stderr,
        )
        return 1

    print("Done.")
    print(f"Set in .env:\nTM_FASTER_WHISPER_MODEL={target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
