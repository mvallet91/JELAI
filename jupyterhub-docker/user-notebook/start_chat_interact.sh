#!/bin/bash
# start_chat_interact.sh - Choose between YDoc and fallback implementations

CHAT_DIR="$1"
LOGS_DIR="$2"

# Check if YDoc is available and USE_YDOC_CHAT is enabled
if [ "$USE_YDOC_CHAT" = "true" ]; then
    echo "Attempting to use YDoc-based chat interaction..."
    
    # Test if YDoc dependencies are available in system Python
    if python -c "import pycrdt, jupyter_ydoc, watchdog" 2>/dev/null; then
        echo "YDoc dependencies found - using chat_interact_ydoc.py"
        exec python /home/jovyan/chat_interact_ydoc.py "$CHAT_DIR" "$LOGS_DIR"
    else
        echo "YDoc dependencies not available - falling back to original implementation"
        exec python /home/jovyan/chat_interact.py "$CHAT_DIR" "$LOGS_DIR"
    fi
else
    echo "USE_YDOC_CHAT disabled - using original implementation"
    exec python /home/jovyan/chat_interact.py "$CHAT_DIR" "$LOGS_DIR"
fi
