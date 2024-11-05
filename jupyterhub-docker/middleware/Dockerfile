# Base Image
FROM python:3.10-slim

# Install Fluentd
RUN apt-get update && \
    apt-get install -y build-essential ruby-full && \
    gem install fluentd --no-document && \
    fluentd --setup /fluent

# Copy Fluentd configuration
COPY td-agent.conf /fluent/etc/td-agent.conf

# Install LLM Handler requirements
COPY middleware_requirements.txt /app/
RUN pip install --no-cache-dir -r /app/middleware_requirements.txt

# Copy LLM Handler code
COPY llm_handler.py /app/llm_handler.py

# Copy any other necessary files (e.g., prompts, utils)
COPY utils.py /app/utils.py

# Copy .env file if needed (be cautious with sensitive data)
COPY .env /app/.env

# Copy the start.sh script and set permissions
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose ports
EXPOSE 24224 8002

# Start Fluentd and LLM Handler
# CMD ["bash", "-c", "\
# fluentd -c /fluent/etc/td-agent.conf -p /fluent/plugins & \
# # uvicorn llm_handler:app --host 0.0.0.0 --port 8002 "]

# Set the CMD to run start.sh
CMD ["/app/start.sh"]
