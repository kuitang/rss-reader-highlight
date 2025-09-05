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

# Run all tests in parallel using pytest-xdist
# -n auto uses all available CPU cores
# -v for verbose output
# --tb=short for shorter tracebacks
echo "Running all tests in parallel with pytest-xdist..."
echo "=================================================="
python -m pytest tests/ -n auto -v --tb=short

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