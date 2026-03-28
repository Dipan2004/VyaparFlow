# =============================================================================
# VyaparFlow - Hugging Face Space Dockerfile
# =============================================================================
# Multi-stage build for optimized image size
# Runs FastAPI backend on port 7860 (Hugging Face requirement)

# Stage 1: Builder
# =============================================================================
FROM python:3.10-slim as builder

WORKDIR /build

# Install system dependencies for build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
# =============================================================================
FROM python:3.13-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:$PATH \
    PORT=7860 \
    NOTIFLOW_DEMO_MODE=true

WORKDIR /app

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local

# Copy entire project
COPY . .

# Create necessary directories with proper permissions
RUN mkdir -p /app/data /app/credentials && \
    chmod -R 755 /app

# Expose Hugging Face default port
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:7860/health || exit 1

# Default command: Run FastAPI with uvicorn
# Listens on 0.0.0.0:7860 (required for Hugging Face Spaces)
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
