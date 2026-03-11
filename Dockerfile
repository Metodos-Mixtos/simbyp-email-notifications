FROM python:3.11-slim

WORKDIR /app

# Set environment for Python output to be unbuffered (good for logging)
ENV PYTHONUNBUFFERED=1

# Set default PORT for Cloud Run (can be overridden at runtime)
ENV PORT=8080

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run as non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Health check for Cloud Run
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/').read()" || exit 1

# Run the application
CMD ["sh", "-c", "exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app"]