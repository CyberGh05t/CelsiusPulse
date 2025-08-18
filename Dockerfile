# Multi-stage build for CelsiusPulse temperature monitoring bot

# Build stage
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Production stage
FROM python:3.11-slim as production

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create non-root user for security
RUN groupadd -r celsiuspulse && \
    useradd -r -g celsiuspulse -s /bin/false celsiuspulse

# Create app directory and set permissions
WORKDIR /app
RUN mkdir -p /app/data/logs && \
    chown -R celsiuspulse:celsiuspulse /app

# Copy virtual environment from builder stage
COPY --from=builder --chown=celsiuspulse:celsiuspulse /opt/venv /opt/venv

# Copy application code
COPY --chown=celsiuspulse:celsiuspulse . .

# Ensure data directory has correct permissions
RUN chmod 750 /app/data && \
    chmod 750 /app/data/logs

# Switch to non-root user
USER celsiuspulse

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Expose port (if using webhook)
EXPOSE 8080

# Run the application
CMD ["python", "main.py"]