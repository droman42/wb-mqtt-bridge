# Define architecture argument with default
ARG ARCH=
ARG LEAN=true

# ===== Build Stage =====
FROM ${ARCH:+$ARCH/}python:3.11-slim-bullseye AS builder

# Set working directory
WORKDIR /build

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    pkg-config \
    libsqlite3-0 \
    zlib1g-dev \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Configure pip to use PiWheels for ARM (as fallback)
RUN mkdir -p /etc/pip && \
    echo "[global]\nextra-index-url=https://www.piwheels.org/simple" > /etc/pip/pip.conf

# Copy source code and UV project files
COPY app/ ./app/
COPY devices/ ./devices/
COPY pyproject.toml uv.lock ./

# Create virtual environment and install dependencies with UV
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=cache,target=/tmp/uv-cache \
    echo "Installing dependencies with UV..." && \
    uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv export --no-dev > requirements.txt && \
    uv pip install --cache-dir=/tmp/uv-cache --requirement requirements.txt

# Set environment path for the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# ===== Final Stage =====
FROM ${ARCH:+$ARCH/}python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PYTHONHASHSEED=1

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi7 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY app/ ./app/
COPY devices/ ./devices/

# Create necessary directories
RUN mkdir -p logs data config

# For lean builds, apply comprehensive optimizations
ARG LEAN=true
RUN if [ "$LEAN" = "true" ]; then \
    echo "Applying comprehensive lean optimizations for Wirenboard..." && \
    # Remove pip cache and other unnecessary files
    rm -rf /root/.cache /tmp/* && \
    # Remove unnecessary Python files
    find /opt/venv -name '__pycache__' -type d -exec rm -rf {} +  2>/dev/null || true && \
    find /opt/venv -name '*.pyc' -delete && \
    find /opt/venv -name '*.pyo' -delete && \
    # Remove development and testing files
    rm -rf /opt/venv/lib/python*/site-packages/*/tests && \
    rm -rf /opt/venv/lib/python*/site-packages/*/test && \
    rm -rf /opt/venv/lib/python*/site-packages/*/testing && \
    rm -rf /opt/venv/lib/python*/site-packages/*/*/tests && \
    rm -rf /opt/venv/lib/python*/site-packages/*/*/test && \
    # Remove documentation and examples
    rm -rf /opt/venv/lib/python*/site-packages/*/docs && \
    rm -rf /opt/venv/lib/python*/site-packages/*/doc && \
    rm -rf /opt/venv/lib/python*/site-packages/*/examples && \
    rm -rf /opt/venv/lib/python*/site-packages/*/example && \
    rm -rf /opt/venv/lib/python*/site-packages/*/samples && \
    rm -rf /opt/venv/lib/python*/site-packages/*/benchmarks && \
    rm -rf /opt/venv/lib/python*/site-packages/*/benchmark && \
    # Remove development tools and build artifacts
    find /opt/venv -name '*.c' -delete && \
    find /opt/venv -name '*.h' -delete && \
    find /opt/venv -name '*.so' -not -path '*/lib*' -delete 2>/dev/null || true && \
    find /opt/venv -name 'Makefile*' -delete && \
    find /opt/venv -name '*.cmake' -delete && \
    find /opt/venv -name 'CMakeFiles' -type d -exec rm -rf {} + 2>/dev/null || true && \
    # Remove setup and installation files
    find /opt/venv -name 'setup.py' -delete && \
    find /opt/venv -name 'setup.cfg' -delete && \
    find /opt/venv -name 'pyproject.toml' -delete && \
    find /opt/venv -name 'MANIFEST.in' -delete && \
    find /opt/venv -name '*.egg-info' -type d -exec rm -rf {} + 2>/dev/null || true && \
    # Remove README and license files
    find /opt/venv -name 'README*' -delete && \
    find /opt/venv -name 'LICENSE*' -delete && \
    find /opt/venv -name 'COPYING*' -delete && \
    find /opt/venv -name 'CHANGELOG*' -delete && \
    find /opt/venv -name 'HISTORY*' -delete && \
    find /opt/venv -name 'NEWS*' -delete && \
    find /opt/venv -name 'AUTHORS*' -delete && \
    find /opt/venv -name 'CONTRIBUTORS*' -delete && \
    # Remove development and CI files  
    find /opt/venv -name '.git*' -delete && \
    find /opt/venv -name '.travis*' -delete && \
    find /opt/venv -name '.github' -type d -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -name 'tox.ini' -delete && \
    find /opt/venv -name '.coveragerc' -delete && \
    find /opt/venv -name 'pytest.ini' -delete && \
    find /opt/venv -name '.pytest_cache' -type d -exec rm -rf {} + 2>/dev/null || true && \
    # Final cleanup
    find /opt/venv -type d -empty -delete 2>/dev/null || true && \
    echo "Lean optimization complete - removed development files, tests, docs, and build artifacts"; \
    fi

# Expose port
EXPOSE 8000

# Health check to monitor container status
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/', timeout=10)" || exit 1

# Command to run the service
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 