FROM ghcr.io/astral-sh/uv:0.13.7-alpine3.23 AS uv

FROM python:3.14-alpine3.23

COPY --from=uv /usr/local/bin/uv /usr/local/bin/uvx /bin/

# Avoid writing .pyc files at runtime and flush application output to container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Precompile installed files during the build and copy them out of uv's cache.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
# Install dependencies before copying source so Docker can reuse this layer when code changes.
RUN uv sync --locked --no-dev --no-install-project

COPY app ./app
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "app.main"]
