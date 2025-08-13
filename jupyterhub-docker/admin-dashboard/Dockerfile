FROM python:3.11-slim-bookworm

# Set working directory
WORKDIR /app

# Copy requirements and install packages
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# Copy application files
COPY app.py /app/
COPY templates/ /app/templates/

# Expose port
EXPOSE 8006

# Start the application
CMD ["python", "app.py"]
