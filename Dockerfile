# Build stage - install dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages to user directory
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage - minimal image
FROM python:3.11-slim

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

WORKDIR /app

# Copy only the app package
COPY app/ ./app/
COPY requirements.txt .

# Create data directory
RUN mkdir -p /data && chmod 755 /data

# Environment setup
ENV PATH=/root/.local/bin:$PATH
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/rss.db
ENV PRODUCTION=true

EXPOSE 8080

# Run as a module
CMD ["python", "-m", "app"]