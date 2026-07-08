from __future__ import annotations

import argparse
import os
from pathlib import Path

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the packaged CaptionFlow backend.")
    parser.add_argument("--host", default=os.environ.get("CAPTIONFLOW_BACKEND_HOST", "127.0.0.1"))
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CAPTIONFLOW_BACKEND_PORT", "0") or "0"),
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("CAPTIONFLOW_BACKEND_LOG_LEVEL", "warning"),
        choices=["critical", "error", "warning", "info", "debug", "trace"],
    )
    return parser.parse_args()


def ensure_parent_dirs() -> None:
    for env_name in ("TM_DATA_DIR", "TM_SQLITE_PATH", "TM_MODELS_DIR", "TM_LOGS_DIR", "TM_SETTINGS_PATH"):
        value = os.environ.get(env_name)
        if not value:
            continue
        path = Path(value).expanduser()
        parent = path if path.suffix == "" else path.parent
        parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    args = parse_args()
    if args.port <= 0:
        raise SystemExit("--port must be a positive integer")
    ensure_parent_dirs()
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        access_log=False,
    )


if __name__ == "__main__":
    main()
