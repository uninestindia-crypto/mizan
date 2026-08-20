FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project definition and source
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Install the package in editable mode
RUN pip install --no-cache-dir -e .

# Expose default web port (7860 for Hugging Face Spaces, 8000 for standard)
EXPOSE 7860

# Set default host and port (configurable via environment variables)
ENV HOST=0.0.0.0
ENV PORT=7860

# Start QuantOS FastAPI web server and UI
CMD ["sh", "-c", "uvicorn quant_system.server.app:app --host ${HOST} --port ${PORT}"]
