# Copyright (c) Jupyter Development Team.
# Fully adapted for JELAI 2025 (by M. Valle)
# Distributed under the terms of the Modified BSD License.

# Configuration file for JupyterHub
import os
import sys
import json
import httpx
import logging
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))
from course_spawner import CourseDockerSpawner
from traitlets.config import get_config

c = get_config()  # noqa: F821

# We rely on environment variables to configure JupyterHub so that we
# avoid having to rebuild the JupyterHub container every time we change a
# configuration parameter.

# --- Core Hub and Spawner Configuration ---
c.JupyterHub.port = 9000
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.image = os.environ["DOCKER_NOTEBOOK_IMAGE"]
network_name = os.environ["DOCKER_NETWORK_NAME"]
c.DockerSpawner.network_name = network_name

c.DockerSpawner.environment = {
    "JUPYTERHUB_SINGLEUSER_APP": "jupyter-server",
    "TA_MIDDLEWARE_URL": "http://middleware:8004"
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

c.DockerSpawner.stop_timeout = 30 

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
# NOTE: Dynamic per-course volumes: Each user+course gets a unique workspace and logs volume.
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
c.NativeAuthenticator.open_signup = True
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
        # TODO: This should be populated dynamically from course data in a real system.
        # For now, hardcoding the teacher user.
        "users": ["teacher1"],
    }
]

# --- Post-auth hook to fetch role & courses from middleware ---
MIDDLEWARE_INTERNAL_USER_INFO = os.environ.get('MIDDLEWARE_USER_INFO_ENDPOINT', 'http://middleware:8005/api/internal/user-info')

async def _fetch_user_info(username: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(MIDDLEWARE_INTERNAL_USER_INFO, params={'username': username})
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


MIDDLEWARE_INTERNAL_USER_INFO = os.environ.get('MIDDLEWARE_USER_INFO_ENDPOINT', 'http://middleware:8005/api/internal/user-info')

async def _fetch_user_info(username: str):
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(MIDDLEWARE_INTERNAL_USER_INFO, params={'username': username})
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None

async def post_auth_hook(authenticator, handler, auth_state):
    """Augment auth_state with role and courses for routing / spawner usage."""
    try:
        username = None
        if isinstance(auth_state, dict):
            username = auth_state.get('name') or auth_state.get('username')
        if not username:
            return auth_state
        info = await _fetch_user_info(username)
        if info:
            auth_state['jelai_role'] = info.get('role')
            auth_state['jelai_teaching'] = info.get('teaching', [])
            auth_state['jelai_enrolled'] = info.get('enrolled', [])
            # Only redirect if not already on the target page
            if (
                hasattr(handler, "redirect") and
                info.get('role') == 'student' and
                info.get('enrolled') and
                not handler.request.path.startswith('/services/learn-dashboard/student-courses')
            ):
                handler.redirect('/services/learn-dashboard/student-courses')
        return auth_state
    except Exception:
        import logging
        logging.exception("Error in post_auth_hook")
        return auth_state

c.Authenticator.post_auth_hook = post_auth_hook

# --- Pre-spawn hook to set environment & volumes per course ---
def pre_spawn_hook(spawner):
    course_id = getattr(spawner, 'course_id', '') or spawner.user_options.get('course_id')
    if course_id:
        spawner.environment['JELAI_COURSE_ID'] = str(course_id)
        base_notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")
        user = spawner.user.name
        spawner.volumes = {
            f"jupyterhub-user-{user}-{course_id}": base_notebook_dir,
            f"jupyterhub-logs-{user}-{course_id}": "/home/jovyan/logs/processed",
            "jupyterhub-docker_shared-resources": {"bind": "/home/jovyan/work/shared_resources", "mode": "ro"}
        }

c.Spawner.pre_spawn_hook = pre_spawn_hook

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