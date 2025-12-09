# Backend Dockerfile for FastAPI
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY prompts/ ./prompts/
COPY tasks/ ./tasks/
COPY data/tasks/ ./data/tasks/
COPY data/skills.json ./data/skills.json
COPY static/ ./static/
COPY templates/ ./templates/

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/submissions

# Create non-root user for security
RUN adduser --system --uid 1001 appuser && \
    chown -R appuser /app
USER appuser

# Expose port (non-standard for Nginx proxy)
EXPOSE 8100

# Run with gunicorn
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8100"]
