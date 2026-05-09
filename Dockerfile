# --- Stage 1: Rust Builder ---
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential pkg-config && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"
RUN pip install maturin

WORKDIR /build
COPY rust_engine/ .
RUN maturin build --release --out /wheels

# --- Stage 2: Runtime ---
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir pytest

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --from=builder /wheels/*.whl .
RUN pip install *.whl && rm *.whl

COPY forge/ forge/
COPY frontend/ frontend/

RUN mkdir -p /tmp/forge_builds
ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["uvicorn", "forge.main:app", "--host", "0.0.0.0", "--port", "8000"]
