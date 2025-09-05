#!/bin/bash

# RSS Reader Test Suite using pytest-xdist for parallel execution

echo "🧪 RSS Reader Parallel Test Suite (pytest-xdist)"
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

# Start server for UI tests
echo "Starting server on port 8080 for UI tests..."
python app.py > test_server.log 2>&1 &
SERVER_PID=$!
sleep 3

# Wait for server to be ready
for i in {1..10}; do
    if curl -s http://localhost:8080 > /dev/null; then
        echo "✅ Server ready on port 8080"
        echo ""
        break
    fi
    sleep 1
done

# Run tests with optimized parallelization:
# - Core tests can run fully parallel (function level)
# - UI test files run in parallel, but tests within each file run serially
echo "Running tests with optimized parallelization..."
echo "=================================================="

# Run core tests with full parallelization
echo "Running core tests (fully parallel)..."
python -m pytest tests/core/ -n auto -v --tb=short

# Run UI tests: files in parallel, tests within files serially
echo ""
echo "Running UI tests (files parallel, tests serial)..."
python -m pytest tests/ui/ -n auto --dist=loadfile -v --tb=short

# Run specialized tests if they exist
echo ""
echo "Running specialized tests..."
python -m pytest tests/specialized/ -v --tb=short || true

# Save exit code
TEST_RESULT=$?

# Kill the server
if [ ! -z "$SERVER_PID" ]; then
    echo ""
    echo "Stopping test server..."
    kill $SERVER_PID 2>/dev/null || true
fi

# Exit with test result
exit $TEST_RESULT