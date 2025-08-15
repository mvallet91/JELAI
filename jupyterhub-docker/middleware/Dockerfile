# Base Image - Use uv for fast installs but install system-wide
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Set the working directory
WORKDIR /app

# Copy pyproject.toml and uv.lock
COPY pyproject.toml /app/
COPY uv.lock /app/

# Install dependencies using proper uv workflow
ENV UV_SYSTEM_PYTHON=1
RUN uv sync --frozen --no-dev

# Runtime stage
FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ruby \
    ruby-dev \
    bash \
    curl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/* 

RUN gem install fluentd --no-document && \
    fluentd --setup /fluent

# Copy Python environment from builder (including venv)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" 

# Copy application code
COPY ea-handler.py ta-handler.py utils.py start.sh .env analytics_cli.py admin_api.py /app/
RUN chmod +x /app/start.sh
COPY inputs/ /app/inputs/

# Fluentd config
RUN mkdir -p /fluent/etc
COPY td-agent.conf /fluent/etc/td-agent.conf

# Expose ports (adding 8005 for admin API)
EXPOSE 24224 8003 8004 8005

# Set the CMD to run start.sh
CMD ["/app/start.sh"]
