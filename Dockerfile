# Build stage - install dependencies
FROM python:3.11.17-slim-trixie as builder

WORKDIR /build

# Install build dependencies if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages to user directory
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage - minimal image
FROM python:3.11.17-slim-trixie
RUN python -m pip install --no-cache-dir --upgrade "pip>=26.2.0" "setuptools>=83.0.0" "wheel>=0.46.2"

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

WORKDIR /app

# Copy the app package and static files
COPY app/ ./app/
COPY static/ ./static/
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