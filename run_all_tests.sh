#!/bin/bash

# RSS Reader Parallel Test Runner using xargs
# Runs tests in parallel with core control

echo "🧪 RSS Reader Parallel Test Suite (using xargs)"
echo "=================================================="

# Ensure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment
source venv/bin/activate

# Kill any existing test servers
pkill -f "python app.py" || true
sleep 1

# Get number of CPU cores
N_CORES=$(nproc)
echo "Running tests on $N_CORES CPU cores"
echo ""

# Create temp directory for test outputs
TEST_DIR=$(mktemp -d)
echo "Test outputs: $TEST_DIR"
echo ""

# Function to run a single test file with its own server if needed
run_test_file() {
    local test_file="$1"
    local test_name=$(basename "$test_file" .py)
    local output_file="$TEST_DIR/${test_name}.txt"
    
    # Determine if test needs its own server
    if [[ "$test_file" == *"test_optimized_integration"* ]] || \
       [[ "$test_file" == *"test_application_startup"* ]] || \
       [[ "$test_file" == *"test_background_worker_integration"* ]]; then
        # Tests that spawn their own servers - use isolated DB
        TEST_DB="$TEST_DIR/${test_name}.db" python -m pytest "$test_file" -v > "$output_file" 2>&1
        result=$?
    else
        # Tests that don't need servers - run directly
        python -m pytest "$test_file" -v > "$output_file" 2>&1
        result=$?
    fi
    
    if [ $result -eq 0 ]; then
        echo "✅ $(basename $test_file)"
        return 0
    else
        echo "❌ $(basename $test_file)"
        return 1
    fi
}

export -f run_test_file
export TEST_DIR

# Find all test files and run them in parallel
echo "Running all tests in parallel..."
echo "=================================================="

find tests -name "test_*.py" -type f | xargs -P $N_CORES -I {} bash -c 'run_test_file "$@"' _ {}

# Generate summary
echo ""
echo "=================================================="
echo "📊 TEST SUMMARY"
echo "=================================================="

# Count results
PASSED=$(grep -l "passed" "$TEST_DIR"/*.txt 2>/dev/null | wc -l)
FAILED=$(grep -l "FAILED\|ERROR" "$TEST_DIR"/*.txt 2>/dev/null | wc -l)
TOTAL=$(ls "$TEST_DIR"/*.txt 2>/dev/null | wc -l)

echo "Tests passed: $PASSED/$TOTAL"

# Show failed tests if any
if [ $FAILED -gt 0 ]; then
    echo ""
    echo "❌ Failed tests:"
    grep -l "FAILED\|ERROR" "$TEST_DIR"/*.txt 2>/dev/null | while read file; do
        basename "$file" .txt
    done
fi

# Show detailed results
echo ""
echo "📈 Detailed Results:"
for file in "$TEST_DIR"/*.txt; do
    if [ -f "$file" ]; then
        name=$(basename "$file" .txt)
        # Extract pytest summary line
        summary=$(grep -E "passed|failed|error|skipped" "$file" | tail -1)
        if [ ! -z "$summary" ]; then
            echo "  $name: $summary"
        fi
    fi
done

echo ""
echo "Full test outputs saved in: $TEST_DIR"
echo "To view a specific test: cat $TEST_DIR/<test_name>.txt"

# Exit with appropriate code
if [ $FAILED -gt 0 ]; then
    exit 1
else
    exit 0
fi