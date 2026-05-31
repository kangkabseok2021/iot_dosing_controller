FROM python:3.12-slim-bookworm AS builder
WORKDIR /build
COPY pyproject.toml .
RUN pip install uv && uv pip install --system --no-cache $(uv pip compile pyproject.toml | grep -v "^#" | tr '\n' ' ')

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY app/ ./app/

HEALTHCHECK CMD python -c \
  "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
