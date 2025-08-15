# Copyright (c) Jupyter Development Team.
# Fully adapted for JELAI 2025 (by M. Valle)
# Distributed under the terms of the Modified BSD License.

# Configuration file for JupyterHub
import os

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
notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")
c.DockerSpawner.notebook_dir = notebook_dir
c.DockerSpawner.volumes = {"jupyterhub-user-{username}": notebook_dir,
                           "jupyterhub-logs-{username}": "/home/jovyan/logs/processed",
                           "jupyterhub-docker_shared-resources": {"bind": "/home/jovyan/work/shared_resources", "mode": "ro"}}
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