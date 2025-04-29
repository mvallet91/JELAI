#!/bin/bash

# Create log directory if it doesn't exist
mkdir -p /var/log/llm-handler/

# Start Fluentd and log output
fluentd -c /fluent/etc/td-agent.conf -p /fluent/plugins > /var/log/llm-handler/fluentd.log 2>&1 &

cd /app

# Start LLM handler app with 4 workers and log output
uvicorn llm_handler:app --workers 4 --host 0.0.0.0 --port 8002 > /var/log/llm-handler/applogshist.txt 2>&1 &

# Wait for any background process to exit
wait -n

# Exit with the status of the first process that exits
exit $?
