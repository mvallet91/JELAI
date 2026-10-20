FROM python:3.11-slim

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml /app/
RUN uv pip install --system -r pyproject.toml

COPY server.py /app/

EXPOSE 8005

ENV HOST=0.0.0.0
ENV PORT=8005

CMD ["mcp", "run", "server.py", "--transport", "sse"]