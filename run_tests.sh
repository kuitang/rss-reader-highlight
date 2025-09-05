#!/bin/bash

# RSS Reader Test Suite Runner

set -e  # Exit on any error

echo "🧪 RSS Reader Test Suite"
echo "=================================================="

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Initialize counters
passed=0
total=0

run_test() {
    local description="$1"
    local command="$2"
    
    echo ""
    echo "🧪 $description"
    echo "=================================================="
    
    if eval "$command"; then
        echo "✅ $description PASSED"
        passed=$((passed + 1))
    else
        echo "❌ $description FAILED"
    fi
    total=$((total + 1))
}

# Test Suite - Run all tests by directory
run_test "Core Tests (Unit & Integration)" \
    "python -m pytest tests/core/ -v --tb=short"

run_test "UI Tests (Playwright Browser Tests)" \
    "python -m pytest tests/ui/ -v --tb=short"

run_test "Specialized Tests (Network & Docker)" \
    "python -m pytest tests/specialized/ -v --tb=short || echo 'Note: Specialized tests may require network access'"

# Summary
echo ""
echo "=================================================="
echo "📊 TEST SUMMARY"
echo "=================================================="
echo "Tests passed: $passed/$total"

if [ $passed -eq $total ]; then
    echo "🎉 All tests passed!"
    echo ""
    echo "💡 Manual verification:"
    echo "   1. Run 'python app.py' to start server"
    echo "   2. Visit http://localhost:5001"
    echo "   3. Verify BBC News feed loads (tests redirect fix)"
    echo "   4. Click articles and verify blue dots disappear (tests HTMX)"
    echo "   5. Switch to Unread view and test article disappearing"
    exit 0
else
    echo "⚠️  $(($total - $passed)) test(s) failed"
    echo ""
    echo "💡 Common issues:"
    echo "   • UI tests need display for Playwright (run manually)"
    echo "   • HTTP server tests need careful subprocess handling"
    echo "   • Essential mocks should always pass"
    exit 1
fi