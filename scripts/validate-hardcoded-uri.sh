#!/bin/bash
# Catch hardcoded MONGO_URI and other environment variables

set -e

# Check for hardcoded SARAPP_MONGO_URI, database URIs, API keys, etc.
HARDCODED_PATTERNS=(
    'SARAPP_MONGO_URI\s*=\s*["\047](?!.*\$\{|.*os\.environ)'
    'mongodb:\/\/[a-zA-Z0-9]'
    'OPENAI_API_KEY\s*='
    'DATABASE_URL\s*='
    'API_KEY\s*='
)

FAILED=0

for file in $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E '\.py$' || true); do
    [ ! -f "$file" ] && continue

    for pattern in "${HARDCODED_PATTERNS[@]}"; do
        if grep -qP "$pattern" "$file" 2>/dev/null; then
            echo "❌ $file: Found hardcoded environment variable or URI"
            echo "   All sensitive config must come from os.environ, not hardcoded"
            FAILED=1
        fi
    done
done

exit $FAILED
