#!/bin/bash
# Check if changes to data/db/sarapp_db/api/routers need cloud_server mirrors

set -e

FAILED=0

for file in $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true); do
    # Only check router files in data/db
    if [[ ! "$file" =~ ^data/db/sarapp_db/api/routers/ ]]; then
        continue
    fi

    # Derive the cloud_server equivalent path
    CLOUD_EQUIV="cloud_server/sarapp_db/api/routers/$(basename "$file")"

    # If data/db router was modified, check if cloud_server has equivalent
    if [[ ! -f "$CLOUD_EQUIV" ]]; then
        echo "⚠️  $file: No mirror found at $CLOUD_EQUIV"
        echo "   Per agents.md: 'When touching routers under data/db/.../routers/, mirror under cloud_server/'"
        echo "   Either create the mirror or confirm this router is data/db-specific"
    fi
done

exit 0  # Don't fail, just warn
