#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="${ROOT}/runtime/whisperkit"
MODEL="${WHISPERKIT_MODEL:-large-v3-v20240930_626MB}"
AUDIO="${SMOKE_AUDIO:-${ROOT}/data/smoke-whisperkit.wav}"

if [ ! -x "${RUNTIME_DIR}/bin/argmax-cli" ]; then
  echo "Missing argmax-cli runtime binary: ${RUNTIME_DIR}/bin/argmax-cli" >&2
  exit 1
fi

if [ ! -d "${RUNTIME_DIR}/Models/whisperkit-coreml/openai_whisper-${MODEL}" ]; then
  echo "Missing WhisperKit model: ${RUNTIME_DIR}/Models/whisperkit-coreml/openai_whisper-${MODEL}" >&2
  exit 1
fi

if [ ! -f "${AUDIO}" ]; then
  echo "Missing smoke audio: ${AUDIO}" >&2
  echo "Set SMOKE_AUDIO to a short wav file, or place one at data/smoke-whisperkit.wav." >&2
  exit 1
fi

PYTHON="${PYTHON:-python}"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-captionflow}"
if command -v conda >/dev/null 2>&1 && conda env list | awk '{print $1}' | grep -qx "${CONDA_ENV_NAME}"; then
  PYTHON="conda run -n ${CONDA_ENV_NAME} python"
fi

cd "${ROOT}"
TM_ASR_BACKEND=whisperkit_server \
TM_WHISPERKIT_EXECUTABLE_PATH="${RUNTIME_DIR}/bin/argmax-cli" \
TM_WHISPERKIT_CLI_WORKDIR="" \
TM_WHISPERKIT_MODEL="${MODEL}" \
TM_WHISPERKIT_MODEL_PATH="${RUNTIME_DIR}/Models/whisperkit-coreml/openai_whisper-${MODEL}" \
TM_WHISPERKIT_STARTUP_TIMEOUT_SECONDS=180 \
PYTHONPATH=backend \
${PYTHON} -u -c "
import os, tempfile, time
from pathlib import Path
from app.asr.factory import asr_config_from_settings, build_transcriber
from app.asr.schemas import TranscribeRequest
from app.core.config import Settings
from app.core.constants import SourceLanguage

audio = Path('${AUDIO}').resolve()
tmpdir = Path(tempfile.mkdtemp(prefix='whisperkit-smoke-'))
output_prefix = tmpdir / 'transcript'
settings = Settings()
config = asr_config_from_settings(settings)
transcriber = build_transcriber(config)
start = time.time()
result = transcriber.transcribe(
    TranscribeRequest(
        audio_path=audio,
        job_dir=tmpdir,
        output_prefix=output_prefix,
        source_language=SourceLanguage.JAPANESE,
    )
)
elapsed = time.time() - start
print(f'OK in {elapsed:.1f}s language={result.language} segments={len(result.segments)}')
print(result.text[:160])
"

echo "WhisperKit smoke test passed."
