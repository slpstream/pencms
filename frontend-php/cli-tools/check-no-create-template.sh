#!/usr/bin/env sh
# Fails if any request-derived value is compiled as a Twig template.
# See gitignore/cms-security-architecture-blueprint.md §4 "the one invariant".

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🔍 Checking for disallowed template compilation primitives under src/..."

if grep -rnE 'createTemplate\s*\(|template_from_string\s*\(' "${ROOT_DIR}/src/"; then
    echo "❌ Security Invariant Error: Disallowed template compilation function found under src/"
    exit 1
fi

echo "✅ Security Invariant Check Passed: No createTemplate() or template_from_string calls in src/."
