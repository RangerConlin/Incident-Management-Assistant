#!/bin/bash
# Warn on UI code that doesn't use shared styles (potential design drift)

set -e

for file in $(git diff --cached --name-only --diff-filter=ACM 2>/dev/null | grep -E 'modules/.*\.py$' || true); do
    [ ! -f "$file" ] && continue

    # Skip non-widget/panel files
    if [[ ! "$file" =~ (widget|panel|dialog) ]]; then
        continue
    fi

    # Check for hardcoded colors (not using palette)
    if grep -qE '#[0-9a-fA-F]{6}|QColor\(["\047]#' "$file"; then
        echo "⚠️  $file: Contains hardcoded colors (potential design drift)"
        echo "   Use utils/styles.py palette helpers instead"
        echo "   Example: from utils.styles import get_palette; palette = get_palette()"
    fi

    # Check for raw QSS strings (should use stylesheet builder)
    if grep -qE 'setStyleSheet\(["\047]' "$file" && ! grep -q 'utils.styles' "$file"; then
        echo "⚠️  $file: Uses inline stylesheets without utils.styles"
        echo "   Consider centralizing styles for consistency"
    fi
done

exit 0
