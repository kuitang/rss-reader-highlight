#!/bin/bash

# RSS Reader Test Suite - Tests manage their own servers via pytest fixtures

echo "🧪 RSS Reader Test Suite"
echo "========================"

# Show help if requested
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: ./run_all_tests.sh [--section SECTION]"
    echo ""
    echo "Sections:"
    echo "  core           - Core logic tests (no server needed)"
    echo "  integration    - Integration tests"
    echo "  ui             - All UI tests (includes isolated)"
    echo "  ui-no-isolated - UI tests excluding isolated tests (faster, for CI)"
    echo "  isolated       - Only isolated/state-sensitive tests"
    echo "  specialized    - Network/Docker integration tests"
    echo "  (none)         - Run all test suites"
    echo ""
    echo "Examples:"
    echo "  ./run_all_tests.sh                      # Run all tests"
    echo "  ./run_all_tests.sh --section core       # Run only core tests"
    echo "  ./run_all_tests.sh --section isolated   # Run only isolated tests"
    exit 0
fi

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

# Create minimal seed database for UI tests if it doesn't exist
if [ ! -f "data/minimal_seed.db" ]; then
    echo "📦 Creating minimal seed database for UI tests..."
    mkdir -p data
    python scripts/create_minimal_db.py
    echo ""
fi

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

run_isolated_tests() {
    echo "🔒 Running isolated tests (state-sensitive)..."
    python -m pytest tests/ui/ $PYTEST_ARGS -v -m isolated
}

run_ui_tests_skip_isolated() {
    echo "🌐 Running UI tests (skipping isolated tests)..."
    python -m pytest tests/ui/ $PYTEST_ARGS -v -m "not isolated"
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
    "ui-no-isolated")
        run_ui_tests_skip_isolated
        ;;
    "isolated")
        run_isolated_tests
        ;;
    "specialized")
        run_specialized_tests
        ;;
    "")
        run_all_tests
        ;;
    *)
        echo "Unknown section: $TEST_SECTION"
        echo "Valid sections: core, integration, ui, ui-no-isolated, isolated, specialized"
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