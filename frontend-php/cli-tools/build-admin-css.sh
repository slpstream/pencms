#!/usr/bin/env bash
#
# Rebuild the prebuilt admin stylesheet (src/admin/css/admin.css).
#
# Uses the Tailwind v3 standalone CLI — no Node, no npm, no Vite.
# Run this when you add a new utility class that is not already in admin.css,
# then commit the generated file. LAN runtime does not need this script.
#
# Usage:
#   ./build-admin-css.sh
#
set -euo pipefail

TAILWIND_VERSION="3.4.17"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"
FRONTEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
STYLE_CSS="${FRONTEND_DIR}/src/admin/css/style.css"
OUT_CSS="${FRONTEND_DIR}/src/admin/css/admin.css"
CONFIG_JS="${SCRIPT_DIR}/tailwind.config.js"
CACHE_DIR="${SCRIPT_DIR}/.cache"
BIN="${CACHE_DIR}/tailwindcss-v${TAILWIND_VERSION}"

if [[ ! -f "${STYLE_CSS}" ]]; then
  echo "error: missing ${STYLE_CSS}" >&2
  exit 1
fi
if [[ ! -f "${CONFIG_JS}" ]]; then
  echo "error: missing ${CONFIG_JS}" >&2
  exit 1
fi

os="$(uname -s)"
arch="$(uname -m)"
case "${os}" in
  Linux)  os_tag="linux" ;;
  Darwin) os_tag="macos" ;;
  *)
    echo "error: unsupported OS '${os}' (need Linux or macOS)" >&2
    exit 1
    ;;
esac
case "${arch}" in
  x86_64|amd64) arch_tag="x64" ;;
  arm64|aarch64) arch_tag="arm64" ;;
  *)
    echo "error: unsupported arch '${arch}'" >&2
    exit 1
    ;;
esac

asset="tailwindcss-${os_tag}-${arch_tag}"
url="https://github.com/tailwindlabs/tailwindcss/releases/download/v${TAILWIND_VERSION}/${asset}"

if [[ ! -x "${BIN}" ]]; then
  echo "▶ Downloading Tailwind standalone CLI v${TAILWIND_VERSION} (${asset})"
  mkdir -p "${CACHE_DIR}"
  tmp="${BIN}.tmp"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 -o "${tmp}" "${url}"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "${tmp}" "${url}"
  else
    echo "error: need curl or wget to download ${url}" >&2
    exit 1
  fi
  chmod +x "${tmp}"
  mv "${tmp}" "${BIN}"
fi

echo "▶ Building admin.css (Tailwind v${TAILWIND_VERSION})"

input="$(mktemp)"
trap 'rm -f "${input}"' EXIT
{
  echo '/* Generated input — do not edit. See build-admin-css.sh */'
  echo '@tailwind base;'
  echo '@tailwind components;'
  echo '@tailwind utilities;'
  echo ''
  cat "${STYLE_CSS}"
} > "${input}"

"${BIN}" \
  --config "${CONFIG_JS}" \
  --input "${input}" \
  --output "${OUT_CSS}" \
  --minify

bytes="$(wc -c < "${OUT_CSS}" | tr -d ' ')"
echo "✅ Wrote ${OUT_CSS} (${bytes} bytes)"
echo "   Commit this file when classes change. LAN boxes do not need Node."
