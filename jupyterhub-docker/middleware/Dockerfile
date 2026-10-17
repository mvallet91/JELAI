# Base Image
FROM ghcr.io/astral-sh/uv:python3.11-bookworm

# Set the working directory
WORKDIR /app

# Copy pyproject
COPY pyproject.toml /app/
COPY uv.lock /app/

# Create venv + install dependencies
ENV UV_SYSTEM_PYTHON=true
RUN uv pip install -r uv.lock --system .

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

# Download the sentence embedding model at build time, so the middleware
# does not need internet access for it at run time.
ARG EMBEDDING_MODEL=all-MiniLM-L6-v2
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

# Copy application code. Secrets come from the environment (see .env.example),
# they are not part of the image.
COPY *.py start.sh /app/
RUN chmod +x /app/start.sh
COPY inputs/ /app/inputs/
# The original configuration is the default for keys that a teacher removes.
COPY inputs/agent_config.yaml /app/defaults/agent_config.yaml
COPY templates/ /app/templates/

# Fluentd config
RUN mkdir -p /fluent/etc
COPY td-agent.conf /fluent/etc/td-agent.conf

# Expose ports 
EXPOSE 24224 8003 8004

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fs http://localhost:8004/health || exit 1

# Set the CMD to run start.sh
CMD ["/app/start.sh"]
