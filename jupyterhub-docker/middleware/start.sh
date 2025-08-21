#!/bin/bash

# Create log directory if it doesn't exist
mkdir -p /var/log/llm-handler/
# Create chat histories directory if it doesn't exist  
mkdir -p /app/chat_histories/

# Start Fluentd and log output
fluentd -c /fluent/etc/td-agent.conf -p /fluent/plugins > /var/log/llm-handler/fluentd.log 2>&1 &

# Change to the app directory
cd /app

# Run seeder to ensure default courses exist (idempotent)
if [ -f ./seed_courses.py ]; then
    echo "Seeding courses..."
    python3 ./seed_courses.py || echo "Seeder failed or already ran"
fi

echo "Starting services..."

# Start EA Handler in the background on port 8003
echo "Starting EA Handler..."
uvicorn ea-handler:app --workers 1  --host 0.0.0.0 --port 8003 > /var/log/llm-handler/ea-logs.txt 2>&1 &
EA_PID=$!

# Start TA Handler in the background on port 8004  
echo "Starting TA Handler..."
uvicorn ta-handler:app --workers 1 --host 0.0.0.0 --port 8004 > /var/log/llm-handler/ta-logs.txt 2>&1 &
TA_PID=$!

# Start Admin API in the background on port 8005
echo "Starting Admin API (FastAPI)..."
uvicorn admin_api:app --workers 1 --host 0.0.0.0 --port 8005 > /var/log/llm-handler/admin-logs.txt 2>&1 &
ADMIN_PID=$!

echo "All services started. PIDs: EA=$EA_PID TA=$TA_PID ADMIN=$ADMIN_PID"

# Keep the container running and monitor services
while true; do
    sleep 10
    
    # Check if processes are still running
    if ! kill -0 $EA_PID 2>/dev/null; then
        echo "EA Handler died, restarting..."
        uvicorn ea-handler:app --workers 1 --host 0.0.0.0 --port 8003 > /var/log/llm-handler/ea-logs.txt 2>&1 &
        EA_PID=$!
    fi
    
    if ! kill -0 $TA_PID 2>/dev/null; then
        echo "TA Handler died, restarting..."
        uvicorn ta-handler:app --workers 1 --host 0.0.0.0 --port 8004 > /var/log/llm-handler/ta-logs.txt 2>&1 &
        TA_PID=$!
    fi
    
    if ! kill -0 $ADMIN_PID 2>/dev/null; then
        echo "Admin API died, restarting..."
        uvicorn admin_api:app --workers 1 --host 0.0.0.0 --port 8005 > /var/log/llm-handler/admin-logs.txt 2>&1 &
        ADMIN_PID=$!
    fi
done
