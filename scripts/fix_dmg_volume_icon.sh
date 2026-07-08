#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ "$#" -gt 0 ]; then
  DMGS=("$@")
else
  DMGS=("${ROOT}"/src-tauri/target/release/bundle/dmg/CaptionFlow_*.dmg)
fi

for dmg in "${DMGS[@]}"; do
  if [ ! -f "${dmg}" ]; then
    echo "DMG not found: ${dmg}" >&2
    exit 1
  fi

  tmp_dir="$(mktemp -d)"
  rw_dmg="${tmp_dir}/captionflow-rw.dmg"
  fixed_dmg="${tmp_dir}/captionflow-fixed.dmg"
  mount_point=""

  cleanup() {
    if [ -n "${mount_point}" ] && mount | grep -q " on ${mount_point} "; then
      hdiutil detach "${mount_point}" -quiet || true
    fi
    rm -rf "${tmp_dir}"
  }
  trap cleanup EXIT

  hdiutil convert "${dmg}" -format UDRW -o "${rw_dmg}" -quiet
  attach_output="$(hdiutil attach "${rw_dmg}" -readwrite -nobrowse -noverify -noautoopen)"
  mount_point="$(
    printf '%s\n' "${attach_output}" |
      awk '/Apple_HFS/ { $1=""; $2=""; sub(/^ +/, ""); print; exit }'
  )"

  if [ -z "${mount_point}" ] || [ ! -d "${mount_point}" ]; then
    echo "Failed to mount ${dmg}" >&2
    printf '%s\n' "${attach_output}" >&2
    exit 1
  fi

  rm -f "${mount_point}/.VolumeIcon.icns" "${mount_point}/.VolumeIcon.ico"
  if command -v SetFile >/dev/null 2>&1; then
    SetFile -a c "${mount_point}" 2>/dev/null || true
  fi
  xattr -d com.apple.FinderInfo "${mount_point}" 2>/dev/null || true

  sync
  hdiutil detach "${mount_point}" -quiet
  mount_point=""

  hdiutil convert "${rw_dmg}" -format UDZO -imagekey zlib-level=9 -o "${fixed_dmg}" -quiet
  mv "${fixed_dmg}" "${dmg}"
  echo "Removed DMG volume icon artifact: ${dmg}"

  trap - EXIT
  rm -rf "${tmp_dir}"
done
