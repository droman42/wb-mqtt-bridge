# Define architecture argument with default
ARG ARCH=
ARG LEAN=false
ARG CRYPTO_VERSION=3.4.8

# ===== Build Stage =====
FROM ${ARCH:+$ARCH/}python:3.11-slim-bullseye AS builder

# Set working directory
WORKDIR /build

# Set environment variables for pip
ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Configure pip to use PiWheels for ARM
RUN mkdir -p /etc/pip && \
    echo "[global]\nextra-index-url=https://www.piwheels.org/simple" > /etc/pip/pip.conf

# Pre-install wheel for package building
RUN pip install --no-cache-dir wheel setuptools pip

# Download pre-built wheels for problematic packages (ARMv7 compatible)
RUN mkdir -p /prebuilt-wheels

# Install cffi first from PyPI (should work without issues)
RUN pip install --no-cache-dir cffi==1.15.1

# Copy only requirements file
COPY requirements.txt ./

# Create a modified requirements file excluding cryptography and broadlink
RUN grep -v "cryptography\|broadlink" requirements.txt > requirements_modified.txt || true

# Install packages from modified requirements first
RUN pip install --no-cache-dir -r requirements_modified.txt

# Try to install cryptography from a specific version
# If this fails, it will fall back to a compatible version
RUN pip install --no-cache-dir cryptography==${CRYPTO_VERSION} || \
    pip install --no-cache-dir cryptography

# Install broadlink (depends on cryptography)
RUN pip install --no-cache-dir broadlink==0.18.0 || \
    pip install --no-cache-dir broadlink

# Create a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install all packages in the virtual environment
RUN pip install --no-cache-dir -r requirements_modified.txt && \
    pip install --no-cache-dir cryptography==${CRYPTO_VERSION} || pip install --no-cache-dir cryptography && \
    pip install --no-cache-dir broadlink==0.18.0

# ===== Final Stage =====
FROM ${ARCH:+$ARCH/}python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PYTHONHASHSEED=1

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libffi7 \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app/ ./app/
COPY devices/ ./devices/

# Create necessary directories
RUN mkdir -p logs config/devices

# For lean builds, set additional optimizations
ARG LEAN=false
RUN if [ "$LEAN" = "true" ]; then \
    echo "Applying lean optimizations for Wirenboard..." && \
    # Remove pip cache and other unnecessary files
    rm -rf /root/.cache && \
    # Remove unnecessary Python files
    find /opt/venv -name '__pycache__' -type d -exec rm -rf {} +  2>/dev/null || true && \
    find /opt/venv -name '*.pyc' -delete && \
    # Remove tests and documentation
    rm -rf /opt/venv/lib/python*/site-packages/*/tests && \
    rm -rf /opt/venv/lib/python*/site-packages/*/docs; \
    fi

# Expose port
EXPOSE 8000

# Command to run the service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"] 