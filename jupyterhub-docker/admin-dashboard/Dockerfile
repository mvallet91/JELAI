FROM python:3.11-slim-bookworm

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml /app/
COPY uv.lock /app/

# Install dependencies
RUN uv sync --frozen

# Copy source code
COPY app.py /app/
COPY templates/ /app/templates/
COPY static/ /app/static/

# Expose port
EXPOSE 8006

# Start the application
CMD ["uv", "run", "python", "app.py"]
