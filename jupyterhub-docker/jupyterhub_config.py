# Copyright (c) Jupyter Development Team.
# Fully adapted for JELAI 2025 (by M. Valle)
# Distributed under the terms of the Modified BSD License.


# Configuration file for JupyterHub
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))
from course_spawner import CourseDockerSpawner
from traitlets.config import get_config

c = get_config()
# We rely on environment variables to configure JupyterHub so that we
# avoid having to rebuild the JupyterHub container every time we change a
# configuration parameter.

# --- Core Hub and Spawner Configuration ---
c.JupyterHub.port = 9000
c.JupyterHub.spawner_class = CourseDockerSpawner

c.DockerSpawner.image = os.environ["DOCKER_NOTEBOOK_IMAGE"]
network_name = os.environ["DOCKER_NETWORK_NAME"]
c.DockerSpawner.network_name = network_name

c.DockerSpawner.environment = {
    "JUPYTERHUB_SINGLEUSER_APP": "jupyter-server",
    "TA_MIDDLEWARE_URL": "http://middleware:8004",
    "MIDDLEWARE_URL": os.environ.get("MIDDLEWARE_URL", "http://middleware:8005")
}

c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.extra_host_config = {'extra_hosts': {'host.docker.internal': 'host-gateway'}}

# --- Resource Management ---
c.JupyterHub.services = [
    {
        "name": "idle-culler",
        "admin": True,
        "command": [
            "python3",
            "-m",
            "jupyterhub_idle_culler",
            "--timeout=1800",  # Shuts down servers after 1800 seconds (30 minutes) of inactivity
        ],
    }
]
c.DockerSpawner.mem_limit = "400M" # Limit memory to 400MB
c.DockerSpawner.cpu_limit = 0.5 # Limit CPU to 0.5 cores


# --- Storage and Data Persistence ---
# Set the notebook directory for DockerSpawner
c.DockerSpawner.notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")

# Use per-course volumes for workspace and logs
def get_per_course_volumes(spawner):
    course_id = getattr(spawner, 'course_id', '') or spawner.user_options.get('course_id', '')
    username = spawner.user.name
    # Always use a string for notebook_dir
    notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")
    volumes = {
        f"jupyterhub-user-{username}-{course_id}": notebook_dir,
        f"jupyterhub-logs-{username}-{course_id}": "/home/jovyan/logs/processed",
        "jupyterhub-docker_shared-resources": {"bind": "/home/jovyan/work/shared_resources", "mode": "ro"}
    }
    return volumes

c.DockerSpawner.notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")
c.DockerSpawner.volumes = {
    "jupyterhub-user-{username}": "/home/jovyan/work",
    "jupyterhub-logs-{username}": "/home/jovyan/logs/processed",
    "jupyterhub-docker_shared-resources": {"bind": "/home/jovyan/work/shared_resources", "mode": "ro"}
}
# NOTE: Dynamic per-course volumes require a custom spawner or post_spawn_hook.
c.JupyterHub.cookie_secret_file = "/data/jupyterhub_cookie_secret"
c.JupyterHub.db_url = "sqlite:////data/jupyterhub.sqlite"

# --- Notebook Server Configuration ---
default_notebook = os.environ.get("DEFAULT_NOTEBOOK")
if default_notebook:
    c.DockerSpawner.default_url = default_notebook

# User containers will access hub by container name on the Docker network
c.JupyterHub.hub_ip = "jupyterhub"
c.JupyterHub.hub_port = 8080

# --- Authentication and Users ---
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"
c.NativeAuthenticator.open_signup = False
admin = os.environ.get("JUPYTERHUB_ADMIN")
if admin:
    c.Authenticator.admin_users = [admin]

# Allow all signed-up users to login
c.Authenticator.allow_all = True

# Define roles for teachers to allow access to the admin dashboard service
c.JupyterHub.load_roles = [
    {
        "name": "teacher",
        "scopes": [
            # Allow access to the service page
            "access:services!service=learn-dashboard",
        ],
        # This should be populated dynamically from course data in a real system.
        # For now, hardcoding the user from the user's report.
        "users": ["teacher1"],
    }
]

# --- Proxied Service: learn-dashboard (served at /services/learn-dashboard/) ---
# Strong token shared with the dashboard so it can call Hub’s API
learn_dashboard_token = os.environ.get("LEARN_DASHBOARD_TOKEN")

if not learn_dashboard_token:
    raise RuntimeError(
        "LEARN_DASHBOARD_TOKEN is not set. Define it in your environment/docker-compose and pass it to both JupyterHub and the admin-dashboard."
    )

c.JupyterHub.services.append({
    "name": "learn-dashboard",                 # URL path: /services/learn-dashboard/
    "url": "http://admin-dashboard:8006",      # internal DNS name:port of the dashboard container
    "oauth_no_confirm": True,                  # skip consent screen
    "api_token": learn_dashboard_token,        # lets the app verify users via Hub API
    "oauth_redirect_uri": "/services/learn-dashboard/oauth_callback",  # path-only redirect URI
})