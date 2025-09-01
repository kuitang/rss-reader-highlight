FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory and set permissions
RUN mkdir -p /data && chmod 755 /data

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/data/rss.db
ENV PRODUCTION=true

# Expose port
EXPOSE 8080

# Initialize SQLite with WAL mode for better performance
RUN sqlite3 /tmp/init.db "PRAGMA journal_mode=WAL; PRAGMA synchronous=1;" && rm /tmp/init.db

# Make production script executable
RUN chmod +x run_production.sh

# Use gunicorn with multiple workers in production
# Falls back to simple uvicorn if gunicorn fails
CMD ["sh", "-c", "./run_production.sh || python app.py"]