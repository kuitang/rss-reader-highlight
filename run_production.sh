#!/bin/bash

# Production server startup script with Gunicorn and multiple workers

# Activate virtual environment
source venv/bin/activate

# Set production environment
export PRODUCTION=true

# Get number of CPU cores
CPU_CORES=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo "2")

# Calculate optimal workers: (2 × CPU_cores) + 1
WORKERS=$((2 * $CPU_CORES + 1))

# But cap at reasonable maximum for this RSS reader app
if [ $WORKERS -gt 9 ]; then
    WORKERS=9
fi

echo "Starting production server with $WORKERS workers (detected $CPU_CORES CPU cores)"

# Run with Gunicorn using Uvicorn workers
# This gives you:
# - Multiple worker processes for handling concurrent requests
# - Automatic worker restart on failure
# - Graceful reloading
# - Better resource utilization

gunicorn app:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT:-8080} \
    --timeout 60 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level info

# Options explained:
# --workers: Number of worker processes
# --worker-class: Use Uvicorn's ASGI worker
# --bind: IP and port to bind to
# --timeout: Worker timeout for handling requests
# --keep-alive: Keep-alive timeout
# --max-requests: Restart workers after this many requests (prevents memory leaks)
# --max-requests-jitter: Randomize worker restarts
# --access-logfile: Where to log requests ('-' means stdout)
# --error-logfile: Where to log errors ('-' means stderr)
# --log-level: Logging verbosity