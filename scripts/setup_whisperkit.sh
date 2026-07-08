#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT}/runtime/whisperkit"
MODEL="${WHISPERKIT_MODEL:-large-v3-v20240930_626MB}"
EXECUTABLE="${RUNTIME_DIR}/bin/argmax-cli"
MODEL_DIR="${RUNTIME_DIR}/Models/whisperkit-coreml/openai_whisper-${MODEL}"

if [ ! -x "${EXECUTABLE}" ] || [ ! -d "${MODEL_DIR}" ]; then
  cat >&2 <<EOF
CaptionFlow now keeps only the minimal WhisperKit runtime in this packaging copy.

Expected files:
  ${EXECUTABLE}
  ${MODEL_DIR}

Build or download WhisperKit elsewhere, then copy only the release argmax-cli
binary and the selected CoreML model into runtime/whisperkit.
EOF
  exit 1
fi

echo "WhisperKit runtime is ready."
echo "Add to .env:"
echo "TM_ASR_BACKEND=whisperkit_server"
echo "TM_WHISPERKIT_EXECUTABLE_PATH=${EXECUTABLE}"
echo "TM_WHISPERKIT_CLI_WORKDIR="
echo "TM_WHISPERKIT_MODEL=${MODEL}"
echo "TM_WHISPERKIT_MODEL_PATH=${MODEL_DIR}"
echo
echo "Then run: ./scripts/smoke_whisperkit.sh"
