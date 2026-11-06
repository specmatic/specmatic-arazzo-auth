FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

FROM python:3.13-slim-bookworm AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY common ./common
COPY services ./services
COPY scripts ./scripts

ARG SERVICE_NAME
ENV SERVICE_NAME=${SERVICE_NAME}
CMD ["sh", "-c", "uvicorn services.${SERVICE_NAME}.app:app --host 0.0.0.0 --port ${PORT:-8000} --ssl-certfile /certs/server.crt --ssl-keyfile /certs/server.key --ssl-ca-certs /certs/ca.crt --ssl-cert-reqs 2"]

