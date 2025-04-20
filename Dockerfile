# Define architecture argument with default
ARG ARCH=

# Use Python 3.11 on Debian Bullseye for Wirenboard 7 compatibility
FROM ${ARCH:+$ARCH/}python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies (minimal set for ARM)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
COPY pyproject.toml .

# Install Python dependencies with platform-specific considerations
RUN pip install --no-cache-dir -r requirements.txt || echo "Continuing despite pip errors - will handle local deps separately"
RUN pip install -e .

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p logs config/devices

# Expose port
EXPOSE 8000

# Set ARM-specific environment variables if needed
ENV PYTHONHASHSEED=1

# Command to run the service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 