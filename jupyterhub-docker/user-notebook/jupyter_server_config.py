import logging

c = get_config()

# Define keywords for INFO logs you want to KEEP.
# Everything else will be hidden.
IMPORTANT_INFO_KEYWORDS = [
    'jupyterlab-pioneer/export',  # Telemetry export confirmation
    'Saving file:',               # Successful file saves
    'YDocExtension',              # Collaboration/sync events
    'CellExecuteEvent',           # Log processor event
    'JupyterHubSingleUser'        # Hub-related info
]

class SelectiveLogFilter(logging.Filter):
    """
    A custom filter to show only important INFO logs while allowing all
    higher-level logs (WARNING, ERROR, CRITICAL).
    """
    def filter(self, record):
        # 1. Always allow logs that are WARNING level or higher.
        if record.levelno > logging.INFO:
            return True

        # 2. For INFO level, check if the message is important.
        if record.levelno == logging.INFO:
            message = record.getMessage()
            # Show if it contains an important keyword OR if it's part of the startup.
            # We approximate "startup" by checking for common startup phrases.
            if any(keyword in message for keyword in IMPORTANT_INFO_KEYWORDS):
                return True
            # Allow initial server startup messages
            if 'Jupyter Server' in message or 'Serving notebooks' in message or 'extension was successfully' in message:
                return True
            # Hide other INFO logs.
            return False
        
        # 3. Allow other logs (like DEBUG if you ever enable it).
        return True

# Apply this filter to the main Jupyter Server logger.
# This ensures it processes all logs from the server.
c.ServerApp.log.addFilter(SelectiveLogFilter())