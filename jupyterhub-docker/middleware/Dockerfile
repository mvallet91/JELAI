# Base Image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS builder

# Enable cache for faster builds
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Set the working directory
WORKDIR /app

# Copy pyproject
COPY pyproject.toml /app/
COPY uv.lock /app/

# Create venv + install dependencies
ENV UV_SYSTEM_PYTHON=true
RUN uv pip install -r uv.lock --system .

# Runtime stage
FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ruby \
    ruby-dev \
    bash \
    curl && \
    rm -rf /var/lib/apt/lists/* 

RUN gem install fluentd --no-document && \
    fluentd --setup /fluent 

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
