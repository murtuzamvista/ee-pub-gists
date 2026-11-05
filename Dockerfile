FROM ghcr.io/astral-sh/uv:0.13.7-alpine3.23 AS uv

FROM python:3.14-alpine3.23

COPY --from=uv /usr/local/bin/uv /usr/local/bin/uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "app.main"]
