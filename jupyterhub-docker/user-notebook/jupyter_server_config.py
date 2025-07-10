import logging

# --- Define the Filter ---
# Keywords for INFO logs you want to KEEP.
IMPORTANT_INFO_KEYWORDS = [
    'jupyterlab-pioneer/export',
    'Serving notebooks from local directory:',
    'Jupyter Server is running at:',
    'Writing Jupyter server cookie secret',
    'extension was successfully'
]

class SelectiveLogFilter(logging.Filter):
    """A custom filter to hide routine logs and show important ones."""
    def filter(self, record):
        # Always show anything that is a WARNING or an ERROR
        if record.levelno > logging.INFO:
            return True
        # For INFO logs, only show them if they contain our important keywords
        if record.levelno == logging.INFO:
            return any(keyword in record.getMessage() for keyword in IMPORTANT_INFO_KEYWORDS)
        return False

# --- Apply the Filter ---
# Get the root logger for the entire Python process
log = logging.getLogger()
# Add our custom filter to it
log.addFilter(SelectiveLogFilter())

# --- Set Log Level ---
# We still need to tell the Jupyter App to process INFO-level logs
c = get_config()
c.Application.log_level = 'INFO'