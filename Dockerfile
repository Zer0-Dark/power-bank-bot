FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# libraqm: Pillow's binary wheel ships WITHOUT Raqm compiled in, but loads the
# system library at runtime if present. Without it Arabic cannot be shaped and
# every card renders as tofu boxes -- `require_shaping()` refuses to start.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libraqm0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first: this layer is cached until pyproject/lock actually change.
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
ENV PATH="/app/.venv/bin:$PATH"

CMD ["python", "-m", "powerbank"]
