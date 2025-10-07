# Build stage
FROM python:3.13-slim AS builder

WORKDIR /build

# Install build dependencies
COPY requirements.txt pyproject.toml ./
COPY src/ ./src/

# Build the package
RUN pip install --no-cache-dir build && \
    python -m build --wheel

# Runtime stage
FROM python:3.13-slim

WORKDIR /app

# Create non-root user
RUN useradd -m -u 1000 airthings && \
    chown -R airthings:airthings /app

# Copy built wheel from builder
COPY --from=builder /build/dist/*.whl /tmp/

# Install the application
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -rf /tmp/*.whl

# Switch to non-root user
USER airthings

# Set Python to run in unbuffered mode
ENV PYTHONUNBUFFERED=1

EXPOSE 8000/tcp

ENTRYPOINT ["airthings-exporter", "--client-id", "${client_id}", "--client-secret", "${client_secret}", "--device-id", "${device_id}"]
