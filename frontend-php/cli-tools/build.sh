#!/usr/bin/env bash
#
# Full static build pipeline for the blog.
# Runs the static site generator, then generates OG images.
#
# Usage:
#   ./build.sh                     # interactive (prompts for domain); builds site "default"
#   ./build.sh --domain example.com
#   ./build.sh --site=wiki --domain wiki.example.com
#   ./build.sh --all-sites         # Pro: one output tree per site id
#
# Extra flags (--site=, --all-sites, --domain, --output) are passed through
# to both steps. og-image-maker.py honors --site=/--all-sites/--output and
# ignores --domain.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "═══════════════════════════════════════════"
echo "  PENCMS // Full Build Pipeline"
echo "═══════════════════════════════════════════"
echo ""

# --- Step 1: Static Site Generation ---
echo "▶ Step 1/2: Static Site Generation"
echo "───────────────────────────────────────────"
php "$SCRIPT_DIR/generate-static.php" "$@"

echo ""

# --- Step 2: OG Image Generation ---
echo "▶ Step 2/2: OG Image Generation"
echo "───────────────────────────────────────────"
python3 "$SCRIPT_DIR/og-image-maker.py" "$@"

echo ""
echo "═══════════════════════════════════════════"
echo "  ✅ Full build pipeline complete."
echo "═══════════════════════════════════════════"
echo ""
