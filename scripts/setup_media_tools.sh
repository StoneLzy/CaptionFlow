#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${ROOT}/runtime/media/bin"
LIB_DIR="${ROOT}/runtime/media/lib"
FFMPEG_BIN="${BIN_DIR}/ffmpeg"
FFPROBE_BIN="${BIN_DIR}/ffprobe"
YTDLP_BIN="${BIN_DIR}/yt-dlp"

MODE="check"
PREFER_BREW=0

for arg in "$@"; do
  case "${arg}" in
    --ensure)
      MODE="ensure"
      ;;
    --from-brew)
      PREFER_BREW=1
      ;;
    --help|-h)
      cat <<EOF
Prepare bundled media tools for CaptionFlow packaging.

Usage:
  ./scripts/setup_media_tools.sh              # verify runtime/media/bin layout
  ./scripts/setup_media_tools.sh --ensure     # download or bundle portable tools
  ./scripts/setup_media_tools.sh --from-brew  # copy from Homebrew without bundling libs

Expected files:
  ${FFMPEG_BIN}
  ${FFPROBE_BIN}
  ${YTDLP_BIN}

On Apple Silicon, --ensure bundles Homebrew ffmpeg/ffprobe with their dylibs.
On Intel macOS, --ensure downloads static ffmpeg/ffprobe builds from evermeet.cx.
EOF
      exit 0
      ;;
    *)
      echo "Unknown argument: ${arg}" >&2
      exit 1
      ;;
  esac
done

ensure_dir() {
  mkdir -p "${BIN_DIR}" "${LIB_DIR}"
}

tool_ready() {
  local path="$1"
  [ -f "${path}" ] && [ -x "${path}" ]
}

tool_runs() {
  local path="$1"
  if ! tool_ready "${path}"; then
    return 1
  fi
  if [ "$(uname -s)" = "Darwin" ] && command -v codesign >/dev/null 2>&1; then
    codesign --verify "${path}" >/dev/null 2>&1 || return 1
  fi
  "${path}" -version >/dev/null 2>&1
}

ytdlp_ready() {
  tool_ready "${YTDLP_BIN}" && "${YTDLP_BIN}" --version >/dev/null 2>&1
}

copy_from_brew() {
  local name="$1"
  local target="$2"
  if ! command -v brew >/dev/null 2>&1; then
    return 1
  fi
  local prefix
  prefix="$(brew --prefix "${name}" 2>/dev/null || true)"
  if [ -z "${prefix}" ]; then
    return 1
  fi
  local source="${prefix}/bin/${name}"
  if [ ! -x "${source}" ]; then
    return 1
  fi
  cp "${source}" "${target}"
  chmod 755 "${target}"
  return 0
}

otool_deps() {
  local image="$1"
  otool -L "${image}" | awk 'NR > 1 {print $1}'
}

is_bundled_dependency() {
  local dep="$1"
  case "${dep}" in
    /opt/homebrew/*|/usr/local/opt/*|/usr/local/Cellar/*)
      [ -f "${dep}" ]
      ;;
    *)
      return 1
      ;;
  esac
}

copy_dependency_graph() {
  local queue=("$@")
  while [ "${#queue[@]}" -gt 0 ]; do
    local image="${queue[0]}"
    queue=("${queue[@]:1}")

    while IFS= read -r dep; do
      if ! is_bundled_dependency "${dep}"; then
        continue
      fi

      local base target
      base="$(basename "${dep}")"
      target="${LIB_DIR}/${base}"
      if [ -f "${target}" ]; then
        continue
      fi

      cp "${dep}" "${target}"
      chmod 755 "${target}"
      queue+=("${target}")
    done < <(otool_deps "${image}")
  done
}

patch_image_dependencies() {
  local image="$1"
  local ref_prefix="$2"

  chmod u+w "${image}"
  while IFS= read -r dep; do
    if ! is_bundled_dependency "${dep}"; then
      continue
    fi

    local base
    base="$(basename "${dep}")"
    install_name_tool -change "${dep}" "${ref_prefix}/${base}" "${image}"
  done < <(otool_deps "${image}")
}

ad_hoc_sign() {
  local image="$1"
  if command -v codesign >/dev/null 2>&1; then
    codesign --force --sign - "${image}" >/dev/null
  fi
}

bundle_brew_ffmpeg() {
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required to bundle ffmpeg on Apple Silicon." >&2
    return 1
  fi
  local prefix
  prefix="$(brew --prefix ffmpeg 2>/dev/null || true)"
  if [ -z "${prefix}" ] || [ ! -x "${prefix}/bin/ffmpeg" ] || [ ! -x "${prefix}/bin/ffprobe" ]; then
    echo "Install ffmpeg first: brew install ffmpeg" >&2
    return 1
  fi

  rm -rf "${LIB_DIR:?}/"*
  cp "${prefix}/bin/ffmpeg" "${FFMPEG_BIN}"
  cp "${prefix}/bin/ffprobe" "${FFPROBE_BIN}"
  chmod 755 "${FFMPEG_BIN}" "${FFPROBE_BIN}"

  copy_dependency_graph "${FFMPEG_BIN}" "${FFPROBE_BIN}"

  if ! compgen -G "${LIB_DIR}/*.dylib" >/dev/null; then
    echo "Bundled ffmpeg did not expose Homebrew dylib dependencies; refusing to continue." >&2
    return 1
  fi

  for dep in "${LIB_DIR}"/*.dylib; do
    local base
    base="$(basename "${dep}")"
    chmod u+w "${dep}"
    install_name_tool -id "@loader_path/${base}" "${dep}" 2>/dev/null || true
    patch_image_dependencies "${dep}" "@loader_path"
  done

  patch_image_dependencies "${FFMPEG_BIN}" "@executable_path/../lib"
  patch_image_dependencies "${FFPROBE_BIN}" "@executable_path/../lib"

  for dep in "${LIB_DIR}"/*.dylib; do
    ad_hoc_sign "${dep}"
  done
  ad_hoc_sign "${FFMPEG_BIN}"
  ad_hoc_sign "${FFPROBE_BIN}"
}

download_ytdlp() {
  curl -fsSL "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos" -o "${YTDLP_BIN}"
  chmod 755 "${YTDLP_BIN}"
  ad_hoc_sign "${YTDLP_BIN}"
}

download_evermeet_binary() {
  local name="$1"
  local target="$2"
  local zip="/tmp/captionflow-${name}.zip"
  curl -fsSL "https://evermeet.cx/ffmpeg/${name}-7.1.zip" -o "${zip}"
  unzip -oq "${zip}" -d "${BIN_DIR}"
  rm -f "${zip}"
  if [ ! -f "${BIN_DIR}/${name}" ]; then
    echo "Downloaded ${name}, but ${BIN_DIR}/${name} was not found." >&2
    exit 1
  fi
  mv -f "${BIN_DIR}/${name}" "${target}"
  chmod 755 "${target}"
  ad_hoc_sign "${target}"
}

ensure_ffmpeg_tools() {
  if tool_runs "${FFMPEG_BIN}" && tool_runs "${FFPROBE_BIN}"; then
    return 0
  fi
  if [ "${MODE}" != "ensure" ]; then
    return 1
  fi

  ensure_dir
  echo "Preparing ffmpeg/ffprobe..."
  rm -f "${FFMPEG_BIN}" "${FFPROBE_BIN}"

  if [ "${PREFER_BREW}" = "1" ]; then
    copy_from_brew "ffmpeg" "${FFMPEG_BIN}"
    copy_from_brew "ffprobe" "${FFPROBE_BIN}"
    ad_hoc_sign "${FFMPEG_BIN}"
    ad_hoc_sign "${FFPROBE_BIN}"
    return 0
  fi

  if [ "$(uname -s)" != "Darwin" ]; then
    copy_from_brew "ffmpeg" "${FFMPEG_BIN}"
    copy_from_brew "ffprobe" "${FFPROBE_BIN}"
    return 0
  fi

  if [ "$(uname -m)" = "arm64" ]; then
    bundle_brew_ffmpeg
    return 0
  fi

  download_evermeet_binary "ffmpeg" "${FFMPEG_BIN}"
  download_evermeet_binary "ffprobe" "${FFPROBE_BIN}"
}

ensure_ytdlp() {
  if ytdlp_ready; then
    return 0
  fi
  if [ "${MODE}" != "ensure" ]; then
    return 1
  fi

  ensure_dir
  echo "Preparing yt-dlp..."
  rm -f "${YTDLP_BIN}"

  if [ "${PREFER_BREW}" = "1" ] && copy_from_brew "yt-dlp" "${YTDLP_BIN}"; then
    return 0
  fi

  if [ "$(uname -s)" = "Darwin" ]; then
    download_ytdlp
    return 0
  fi

  copy_from_brew "yt-dlp" "${YTDLP_BIN}"
}

ensure_dir
ensure_ffmpeg_tools
ensure_ytdlp

if command -v xattr >/dev/null 2>&1; then
  xattr -dr com.apple.quarantine "${BIN_DIR}" "${LIB_DIR}" 2>/dev/null || true
fi

if tool_runs "${FFMPEG_BIN}" && tool_runs "${FFPROBE_BIN}" && ytdlp_ready; then
  echo "Media tools are ready under runtime/media/."
  echo
  echo "Optional .env overrides for local dev:"
  echo "TM_FFMPEG_EXECUTABLE=${FFMPEG_BIN}"
  echo "TM_FFPROBE_EXECUTABLE=${FFPROBE_BIN}"
  echo "TM_YTDLP_EXECUTABLE=${YTDLP_BIN}"
  exit 0
fi

cat >&2 <<EOF
CaptionFlow media tools are not ready.

Expected files:
  ${FFMPEG_BIN}
  ${FFPROBE_BIN}
  ${YTDLP_BIN}

Run:
  ./scripts/setup_media_tools.sh --ensure
EOF
exit 1
