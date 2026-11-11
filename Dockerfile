# ==============================================================================
# LLM UUM — Academic & Circular Intelligence System Dockerfile
# Multi-Format RAG & 3-Pane Document Intelligence Platform
# ==============================================================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

# Install system dependencies required for PDF parsing and OCR extraction:
# - poppler-utils: pdftotext, pdfinfo, pdftoppm, pdfimages
# - tesseract-ocr: image & scanned PDF OCR fallback
# - curl: container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency requirements first to leverage Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code and resources
COPY . /app

# Ensure volume mount target directories exist and make entrypoint executable
RUN mkdir -p /app/data /app/circular_forms && chmod +x /app/docker-entrypoint.sh

# Expose web server ports (8000: Starlette SPA, 8501: Streamlit Dashboard)
EXPOSE 8000 8501

# Run entrypoint
ENTRYPOINT ["/app/docker-entrypoint.sh"]

