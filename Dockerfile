FROM python:3.11-slim AS base

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY omnirag/ omnirag/

RUN pip install --no-cache-dir -e .

EXPOSE 8100

CMD ["omnirag", "serve", "--host", "0.0.0.0", "--port", "8100"]
