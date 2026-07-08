#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="${ROOT}/runtime/backend"
OUTPUT_NAME="captionflow-backend"

choose_python() {
  if command -v conda >/dev/null 2>&1; then
    if conda env list | awk '{print $1}' | grep -qx "captionflow"; then
      echo "conda run -n captionflow python"
      return
    fi
    if conda env list | awk '{print $1}' | grep -qx "translation-middleware"; then
      echo "conda run -n translation-middleware python"
      return
    fi
  fi
  echo "${PYTHON:-python}"
}

mkdir -p "${OUTPUT_DIR}"
PYTHON_COMMAND="$(choose_python)"

if ! ${PYTHON_COMMAND} -c "import PyInstaller" >/dev/null 2>&1; then
  cat >&2 <<EOF
PyInstaller is required to build the backend runtime.

Install project dev dependencies first:
  python -m pip install -e ".[dev]"

Selected Python command was:
  ${PYTHON_COMMAND}
EOF
  exit 1
fi

cd "${ROOT}"
rm -rf build/captionflow-backend dist/captionflow-backend "${OUTPUT_DIR}/${OUTPUT_NAME}"
PYTHONPATH=backend ${PYTHON_COMMAND} -m PyInstaller \
  --clean \
  --noconfirm \
  --onedir \
  --name captionflow-backend \
  --distpath dist \
  --workpath build \
  --specpath build \
  --paths backend \
  --collect-submodules uvicorn \
  --hidden-import app.main \
  --hidden-import uvicorn.logging \
  --hidden-import uvicorn.loops.auto \
  --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto \
  --hidden-import uvicorn.lifespan.on \
  --exclude-module av \
  --exclude-module faster_whisper \
  --exclude-module mlx \
  --exclude-module mlx_whisper \
  --exclude-module numba \
  --exclude-module numpy \
  --exclude-module onnxruntime \
  --exclude-module scipy \
  --exclude-module torch \
  backend/app/sidecar.py

ditto "dist/captionflow-backend" "${OUTPUT_DIR}/${OUTPUT_NAME}"
chmod +x "${OUTPUT_DIR}/${OUTPUT_NAME}/captionflow-backend"
echo "Built backend runtime: ${OUTPUT_DIR}/${OUTPUT_NAME}/captionflow-backend"
