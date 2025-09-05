#!/bin/bash

# RSS Reader Test Suite using native pytest server management

echo "🧪 RSS Reader Native pytest Test Suite"
echo "======================================="

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

# Get number of CPU cores
N_CORES=$(nproc)
echo "Running tests on $N_CORES CPU cores with native pytest server management"
echo ""

# Run tests based on section argument - now using native pytest fixtures
run_all_tests() {
    # Run core tests with full parallelization (MINIMAL_MODE managed by conftest.py)
    echo "🔬 Running core tests (fully parallel, no server needed)..."
    python -m pytest tests/core/ -n auto
    CORE_RESULT=$?
    
    # Run UI tests: files in parallel with server per worker (managed by conftest.py)
    echo ""
    echo "🌐 Running UI tests (files parallel, server per worker)..."
    python -m pytest tests/ui/ -n auto --dist=loadfile
    UI_RESULT=$?
    
    # Run specialized tests in parallel per file (some may need network)
    echo ""
    echo "⚙️  Running specialized tests (files parallel)..."
    python -m pytest tests/specialized/ -n auto --dist=loadfile
    SPEC_RESULT=$?
    
    # Return failure if any test suite failed
    if [ $CORE_RESULT -ne 0 ] || [ $UI_RESULT -ne 0 ] || [ $SPEC_RESULT -ne 0 ]; then
        return 1
    fi
    return 0
}

run_core_tests() {
    echo "🔬 Running core tests (fully parallel, no server needed)..."
    python -m pytest tests/core/ -n auto
}

run_ui_tests() {
    echo "🌐 Running UI tests (files parallel, server per worker)..."
    python -m pytest tests/ui/ -n auto --dist=loadfile
}

run_specialized_tests() {
    echo "⚙️  Running specialized tests (files parallel)..."
    python -m pytest tests/specialized/ -n auto --dist=loadfile
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
    "")
        run_all_tests
        ;;
    *)
        echo "Unknown section: $TEST_SECTION"
        echo "Valid sections: core, ui, specialized"
        exit 1
        ;;
esac

# Save exit code
TEST_RESULT=$?

# Native pytest handles all cleanup through fixtures and hooks
echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed (exit code: $TEST_RESULT)"
fi

exit $TEST_RESULT