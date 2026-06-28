#!/bin/bash
# Catch direct MongoDB access in UI code (violation of UI -> API -> MongoDB architecture)

set -e

FAILED=0

for file in $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E '\.py$' || true); do
    [ ! -f "$file" ] && continue

    # Skip routers and repository files (they're allowed direct DB access)
    if [[ "$file" =~ (repository|routers?|database|db\.py) ]]; then
        continue
    fi

    # Skip if it's in data/db/ (that's the data layer)
    if [[ "$file" =~ ^data/db/ ]]; then
        continue
    fi

    # Check for direct collection operations
    PATTERNS=(
        '\.insert_one\('
        '\.insert_many\('
        '\.update_one\('
        '\.update_many\('
        '\.delete_one\('
        '\.delete_many\('
        '\.find\('
        '\.find_one\('
    )

    # Look for patterns AFTER checking if accessing db/collection
    for pattern in "${PATTERNS[@]}"; do
        if grep -qE "(\[.db\[|\.collection\(|MongoClient|pymongo\.)" "$file" && grep -qE "$pattern" "$file"; then
            # Make sure it's not in a comment
            if grep -v '^\s*#' "$file" | grep -qE "(\[.db\[|\.collection\(|MongoClient)" && grep -v '^\s*#' "$file" | grep -qE "$pattern"; then
                echo "❌ $file: Found direct MongoDB access outside data/db/"
                echo "   Architecture: UI -> API (data/db) -> MongoDB"
                echo "   Use utils/api_client.py to call API endpoints instead"
                FAILED=1
                break
            fi
        fi
    done
done

exit $FAILED
