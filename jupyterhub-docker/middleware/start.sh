#!/bin/bash

# Create log directory if it doesn't exist
mkdir -p /var/log/llm-handler/

# Start Fluentd and log output
fluentd -c /fluent/etc/td-agent.conf -p /fluent/plugins > /var/log/llm-handler/fluentd.log 2>&1 &

# Change to the app directory
cd /app

# Number of worker processes per agent. Each TA worker loads the embedding model.
TA_WORKERS="${TA_WORKERS:-2}"
EA_WORKERS="${EA_WORKERS:-2}"

# Start EA Handler in the background on port 8003
uvicorn ea-handler:app --workers "$EA_WORKERS" --host 0.0.0.0 --port 8003 2>&1 | tee -a /var/log/llm-handler/ea-logs.txt &

# Start TA Handler in the background on port 8004
uvicorn ta-handler:app --workers "$TA_WORKERS" --host 0.0.0.0 --port 8004 2>&1 | tee -a /var/log/llm-handler/ta-logs.txt &

# Wait for any background process to exit
wait -n

# Exit with the status of the first process that exits
exit $?
