FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

LABEL io.modelcontextprotocol.server.name="io.github.feodor-ra/printables-mcp"

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY README.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-editable

RUN useradd --create-home --uid 10001 app
USER app

ENTRYPOINT ["/app/.venv/bin/printables-mcp"]
