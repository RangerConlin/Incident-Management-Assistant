#!/bin/bash
# Fail if web_client's generated status-color CSS is stale relative to its
# Python source (styles/profiles/dark.py / light.py). See
# scripts/generate_web_status_colors.py and web_client/AGENTS.md's "Status
# colors" entry.

set -e

cd "$(dirname "$0")/.."

if ! python3 scripts/generate_web_status_colors.py --check; then
    echo "❌ web_client/src/styles/statusColors.css is out of date."
    echo "   Run: python3 scripts/generate_web_status_colors.py"
    exit 1
fi

exit 0
