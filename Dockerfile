# Define architecture argument with default
ARG ARCH=
ARG LEAN=true

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
    libsqlite3-0 \
    zlib1g-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Configure pip to use PiWheels for ARM
RUN mkdir -p /etc/pip && \
    echo "[global]\nextra-index-url=https://www.piwheels.org/simple" > /etc/pip/pip.conf

# Copy only requirements file
COPY requirements.txt ./

# Create a virtual environment early and set PATH
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install core packages individually to isolate any failures
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing fastapi..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "fastapi>=0.103.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing uvicorn..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "uvicorn>=0.23.2"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing pydantic..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "pydantic>=2.11.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing python-dotenv..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "python-dotenv>=1.0.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing typing_extensions..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "typing_extensions>=4.7.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing aiomqtt..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "aiomqtt>=1.0.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing paho-mqtt..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "paho-mqtt>=1.6.1"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing aiohttp..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "aiohttp>=3.8.1"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing pyyaml..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "pyyaml>=6.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing jsonschema..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "jsonschema>=4.4.0"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing httpx..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary httpx

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing requests..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary requests

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing websockets..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "websockets>=10.2"

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing openhomedevice from fork..." && \
    pip install --cache-dir=/tmp/pip-cache \
        git+https://github.com/droman42/openhomedevice.git

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing pyOpenSSL..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary "pyOpenSSL>=23.2.0"

# Install cryptography separately with ARM-specific handling
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing cryptography for ARM..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary \
        cryptography>=40.0

# Install broadlink after cryptography
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing broadlink..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary \
        broadlink==0.18.0

# Install Git dependencies one by one to isolate any failures
RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing pyatv..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary \
        git+https://github.com/postlund/pyatv.git@f75e718bc0bdaf0a3ff06eb00086f781b3f06347#egg=pyatv

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing pymotivaxmc2..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary \
        git+https://github.com/droman42/pymotivaxmc2.git

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing asyncwebostv..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary \
        git+https://github.com/droman42/asyncwebostv.git

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=cache,target=/tmp/pip-cache \
    echo "Installing asyncmiele..." && \
    pip install --cache-dir=/tmp/pip-cache --prefer-binary \
        git+https://github.com/droman42/asyncmiele.git

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
    libffi7 \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY app/ ./app/
COPY devices/ ./devices/

# Create necessary directories
RUN mkdir -p logs data config

# For lean builds, set additional optimizations
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