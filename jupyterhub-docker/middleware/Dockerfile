# Base Image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm

# Set the working directory
WORKDIR /app

# Copy pyproject
COPY pyproject.toml /app/

# Create venv + install dependencies
RUN uv venv && uv pip install .

# Copy code
COPY ea-handler.py ta-handler.py utils.py start.sh td-agent.conf .env /app/
RUN chmod +x /app/start.sh
# Copy all contents of inputs directory
COPY inputs/ /app/inputs/

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    ruby \
    ruby-dev \
    # linux-headers \
    bash \
    curl && \
    gem install fluentd --no-document && \
    fluentd --setup /fluent

# Fluentd config
RUN mkdir -p /fluent/etc
COPY td-agent.conf /fluent/etc/td-agent.conf

# Expose ports 
EXPOSE 24224 8003 8004

# Set the CMD to run start.sh
CMD ["/app/start.sh"]
