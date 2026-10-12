#!/bin/bash
# Fail if apps/web's generated status-color CSS is stale relative to its
# Python source (styles/profiles/dark.py / light.py). See
# tools/scripts/generate_web_status_colors.py and apps/web/AGENTS.md's "Status
# colors" entry.

set -e

cd "$(dirname "$0")/../.."

if ! python3 tools/scripts/generate_web_status_colors.py --check; then
    echo "apps/web/src/styles/statusColors.css is out of date."
    echo "   Run: python3 tools/scripts/generate_web_status_colors.py"
    exit 1
fi

exit 0
