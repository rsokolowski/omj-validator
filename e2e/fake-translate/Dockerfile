# Fake Translation API Server Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY server.py .
RUN chmod 644 server.py

# Create non-root user
RUN adduser --system --uid 1001 appuser
USER appuser

EXPOSE 8081

CMD ["python", "server.py"]
