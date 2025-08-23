
from traitlets.config import get_config
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

# Inject custom JS to hide the Services tab for all users
import os
from notebook.utils import url_path_join
from notebook.base.handlers import IPythonHandler
import tornado.web

def _inject_hide_services_tab_for_students():
    # Only inject the JS for students (not teachers or admins)
    user_role = os.environ.get('JELAI_USER_ROLE', '').lower()
    if user_role != 'student':
        return
    class HideServicesTabHandler(IPythonHandler):
        @tornado.web.authenticated
        def get(self):
            js_path = os.path.join(os.path.dirname(__file__), 'static', 'hide_services_tab.js')
            self.set_header('Content-Type', 'application/javascript')
            with open(js_path, 'r') as f:
                self.write(f.read())

    def load_jupyter_server_extension(nbapp):
        web_app = nbapp.web_app
        route_pattern = url_path_join(web_app.settings['base_url'], '/static/hide_services_tab.js')
        web_app.add_handlers('.*', [(route_pattern, HideServicesTabHandler)])
    c.NotebookApp.server_extensions = getattr(c.NotebookApp, 'server_extensions', []) + [load_jupyter_server_extension]

_inject_hide_services_tab_for_students()