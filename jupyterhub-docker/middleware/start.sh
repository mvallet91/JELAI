#!/bin/bash

# Create log directory if it doesn't exist
mkdir -p /var/log/llm-handler/

# Start Fluentd and log output
fluentd -c /fluent/etc/td-agent.conf -p /fluent/plugins > /var/log/llm-handler/fluentd.log 2>&1 &

# Change to the app directory
cd /app


# Start EA Handler in the background on port 8003
uvicorn ea-handler:app --workers 4  --host 0.0.0.0 --port 8003 > /var/log/llm-handler/ea-logs.txt 2>&1 &

# Start TA Handler in the background on port 8004
uvicorn ta-handler:app --workers 4 --host 0.0.0.0 --port 8004 > /var/log/llm-handler/ta-logs.txt 2>&1 &

# Start Admin API in the background on port 8005
python admin_api.py > /var/log/llm-handler/admin-logs.txt 2>&1 &

# Wait for any background process to exit
wait -n

# Exit with the status of the first process that exits
exit $?
