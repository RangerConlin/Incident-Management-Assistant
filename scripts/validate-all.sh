#!/bin/bash
# Comprehensive repo validation for agents
# Runs all checks and reports summary

set -e

FAIL_COUNT=0
WARN_COUNT=0
PASS_COUNT=0

echo "🔍 Validating Incident Management Assistant repo..."
echo ""

# Run each validator and capture results
run_validator() {
    local name=$1
    local script=$2

    if [ ! -f "$script" ]; then
        echo "⚠️  Missing: $script"
        return
    fi

    echo "Running: $name"
    if bash "$script" 2>&1 | tee /tmp/validator_out.txt; then
        echo "✅ $name: PASS"
        ((PASS_COUNT++))
    else
        exit_code=$?
        output=$(cat /tmp/validator_out.txt)

        # Check if it's a warning (exit 0 but had warnings) or failure
        if echo "$output" | grep -q "^❌"; then
            echo "❌ $name: FAIL"
            ((FAIL_COUNT++))
        else
            echo "⚠️  $name: WARNINGS"
            ((WARN_COUNT++))
        fi
    fi
    echo ""
}

run_validator "Hardcoded URIs" "scripts/validate-hardcoded-uri.sh"
run_validator "Direct DB Access" "scripts/validate-direct-db-access.sh"
run_validator "Structure Rules" "scripts/validate-structure.sh"
run_validator "UI Styling" "scripts/validate-ui-styles.sh"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Passed: $PASS_COUNT"
echo "⚠️  Warnings: $WARN_COUNT"
echo "❌ Failed: $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -gt 0 ]; then
    echo "❌ Validation FAILED. Fix errors before committing."
    exit 1
elif [ $WARN_COUNT -gt 0 ]; then
    echo "⚠️  Validation passed with warnings. Review above."
    exit 0
else
    echo "✅ All checks passed!"
    exit 0
fi
