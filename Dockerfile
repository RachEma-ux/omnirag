# ── Stage 1: build deps ──
FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY omnirag/ omnirag/

RUN pip install --no-cache-dir --prefix=/install -e ".[qdrant]" && \
    pip install --no-cache-dir --prefix=/install asyncpg httpx

# ── Stage 2: runtime ──
FROM python:3.11-slim

RUN groupadd -r omnirag && useradd -r -g omnirag -d /app omnirag

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --from=builder /app /app

RUN chown -R omnirag:omnirag /app

USER omnirag

ENV PYTHONUNBUFFERED=1
EXPOSE 8100

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8100/health')" || exit 1

CMD ["omnirag", "serve", "--host", "0.0.0.0", "--port", "8100"]
