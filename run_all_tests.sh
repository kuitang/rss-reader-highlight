#!/bin/bash

# RSS Reader Test Suite - Requires manual server startup for UI tests

echo "🧪 RSS Reader Test Suite"
echo "========================"
echo ""
echo "⚠️  UI TESTS REQUIRE RUNNING SERVER ⚠️"
echo "Start server before running UI tests:"
echo "  python app.py  (or MINIMAL_MODE=true python app.py)"
echo ""

# Parse command line arguments
TEST_SECTION=""
if [ "$1" = "--section" ] && [ -n "$2" ]; then
    TEST_SECTION="$2"
    echo "Running only $TEST_SECTION tests"
    echo ""
fi

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Running tests with file-level parallelization to reduce conflicts
echo "Running tests with file-level parallelization (--dist=loadfile) to reduce conflicts"
echo "To skip server-dependent tests: pytest -m 'not needs_server'"
echo ""

# Run tests based on section argument
run_all_tests() {
    # Run core tests with file-level parallelization
    echo "🔬 Running core tests (file-level parallelization)..."
    python -m pytest tests/core/ -n auto --dist=loadfile
    CORE_RESULT=$?
    
    # Run UI tests with file-level parallelization
    echo ""
    echo "🌐 Running UI tests (file-level parallelization)..."
    python -m pytest tests/ui/ -n auto --dist=loadfile
    UI_RESULT=$?
    
    # Run specialized tests with file-level parallelization
    echo ""
    echo "⚙️  Running specialized tests (file-level parallelization)..."
    python -m pytest tests/specialized/ -n auto --dist=loadfile
    SPEC_RESULT=$?
    
    # Run integration tests (currently skipped)
    echo ""
    echo "🔗 Running integration tests (currently skipped)..."
    python -m pytest tests/integration/ -n auto --dist=loadfile
    INTEGRATION_RESULT=$?
    
    # Return failure if any test suite failed
    if [ $CORE_RESULT -ne 0 ] || [ $UI_RESULT -ne 0 ] || [ $SPEC_RESULT -ne 0 ] || [ $INTEGRATION_RESULT -ne 0 ]; then
        return 1
    fi
    return 0
}

run_core_tests() {
    echo "🔬 Running core tests (file-level parallelization)..."
    python -m pytest tests/core/ -n auto --dist=loadfile
}

run_ui_tests() {
    echo "🌐 Running UI tests (file-level parallelization)..."
    python -m pytest tests/ui/ -n auto --dist=loadfile
}

run_specialized_tests() {
    echo "⚙️  Running specialized tests (file-level parallelization)..."
    python -m pytest tests/specialized/ -n auto --dist=loadfile
}

run_integration_tests() {
    echo "🔗 Running integration tests (currently skipped)..."
    python -m pytest tests/integration/ -n auto --dist=loadfile
}

# Main execution based on section
case "$TEST_SECTION" in
    "core")
        run_core_tests
        ;;
    "ui")
        run_ui_tests
        ;;
    "specialized")
        run_specialized_tests
        ;;
    "integration")
        run_integration_tests
        ;;
    "")
        run_all_tests
        ;;
    *)
        echo "Unknown section: $TEST_SECTION"
        echo "Valid sections: core, ui, specialized, integration"
        exit 1
        ;;
esac

# Save exit code
TEST_RESULT=$?

# Tests with @pytest.mark.needs_server require manual server startup
echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed (exit code: $TEST_RESULT)"
fi

exit $TEST_RESULT