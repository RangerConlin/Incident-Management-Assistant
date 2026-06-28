#!/bin/bash
# Catch structural violations: no QML files, no backend/ dir, no nested AGENTS without reason

set -e

FAILED=0

for file in $(git diff --cached --name-only --diff-filter=A 2>/dev/null || true); do
    # No .qml files
    if [[ "$file" =~ \.qml$ ]]; then
        echo "❌ $file: New QML files are not allowed"
        echo "   See CLAUDE.md: 'No new QML files. Treat existing QML-facing bridges as legacy.'"
        FAILED=1
    fi

    # No backend/ directory
    if [[ "$file" =~ ^backend/ ]]; then
        echo "❌ $file: No backend/ directory allowed"
        echo "   Use: modules/, lan_server/, cloud_server/, server/, or data/"
        FAILED=1
    fi

    # Warn on new nested AGENTS.md (shouldn't happen often)
    if [[ "$file" == "AGENTS.md" && "$file" != "agents.md" ]]; then
        echo "⚠️  $file: New nested AGENTS.md detected"
        echo "   Confirm this follows agents.md guidance on nested rules"
    fi
done

exit $FAILED
