FROM python:3.14-alpine3.23 AS python-base

FROM ghcr.io/astral-sh/uv:0.13.7-alpine3.23 AS uv

FROM python-base AS build

COPY --from=uv /usr/local/bin/uv /usr/local/bin/uvx /bin/

# Copy packages from uv's cache into the virtual environment.
ENV UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
# Install dependencies before copying source so Docker can reuse this layer when code changes.
RUN uv sync --locked --no-dev --no-install-project --no-cache

COPY app ./app
# Install the application as a wheel so runtime doesn't need the source tree.
RUN uv sync --locked --no-dev --no-cache --no-editable

FROM python-base AS runtime

# Avoid writing .pyc files at runtime and flush application output to container logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY --from=build /app/.venv /app/.venv

USER 10001:10001

EXPOSE 8080

CMD ["python", "-m", "app.main"]
