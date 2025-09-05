#!/bin/bash

# RSS Reader Test Suite - Tests manage their own servers via pytest fixtures

echo "🧪 RSS Reader Test Suite"
echo "========================"

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

# Use pytest-xdist for parallelization
PYTEST_ARGS="-n auto --dist=loadfile"

echo ""

# Run tests based on section argument - tests auto-start their own servers
run_all_tests() {
    # Run core tests (no server needed)
    echo "🔬 Running core tests..."
    python -m pytest tests/core/ $PYTEST_ARGS -v
    CORE_RESULT=$?
    
    # Run integration tests
    echo ""
    echo "🔗 Running integration tests..."
    python -m pytest tests/integration/ $PYTEST_ARGS -v
    INTEGRATION_RESULT=$?
    
    # Run UI tests (auto-start servers via conftest.py)
    echo ""
    echo "🌐 Running UI tests..."
    python -m pytest tests/ui/ $PYTEST_ARGS -v
    UI_RESULT=$?
    
    # Run specialized tests (network/docker)
    echo ""
    echo "⚙️  Running specialized tests..."
    python -m pytest tests/specialized/ $PYTEST_ARGS -v
    SPEC_RESULT=$?
    
    # Return failure if any test suite failed
    if [ $CORE_RESULT -ne 0 ] || [ $INTEGRATION_RESULT -ne 0 ] || [ $UI_RESULT -ne 0 ] || [ $SPEC_RESULT -ne 0 ]; then
        return 1
    fi
    return 0
}

run_core_tests() {
    echo "🔬 Running core tests..."
    python -m pytest tests/core/ $PYTEST_ARGS -v
}

run_integration_tests() {
    echo "🔗 Running integration tests..."
    python -m pytest tests/integration/ $PYTEST_ARGS -v
}

run_ui_tests() {
    echo "🌐 Running UI tests..."
    python -m pytest tests/ui/ $PYTEST_ARGS -v
}

run_specialized_tests() {
    echo "⚙️  Running specialized tests..."
    python -m pytest tests/specialized/ $PYTEST_ARGS -v
}

# Main execution based on section
case "$TEST_SECTION" in
    "core")
        run_core_tests
        ;;
    "integration")
        run_integration_tests
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
        echo "Valid sections: core, integration, ui, specialized"
        exit 1
        ;;
esac

# Save exit code
TEST_RESULT=$?

# Tests handle their own cleanup via pytest fixtures
echo ""
if [ $TEST_RESULT -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Some tests failed"
fi

exit $TEST_RESULT