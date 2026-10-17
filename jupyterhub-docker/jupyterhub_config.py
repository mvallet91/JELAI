# Copyright (c) Jupyter Development Team.
# Fully adapted for JELAI 2025 (by M. Valle)
# Distributed under the terms of the Modified BSD License.

# Configuration file for JupyterHub
import os

c = get_config()  # noqa: F821

# We rely on environment variables to configure JupyterHub so that we
# avoid having to rebuild the JupyterHub container every time we change a
# configuration parameter.


def _env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _read_secret(env_name, file_env_name):
    """Return a secret from an environment variable or from a file."""
    value = os.environ.get(env_name, "").strip()
    path = os.environ.get(file_env_name, "")
    if not value and path and os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            value = f.read().strip()
    return value


# --- Core Hub and Spawner Configuration ---
c.JupyterHub.port = 8000
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.image = os.environ["DOCKER_NOTEBOOK_IMAGE"]
network_name = os.environ["DOCKER_NETWORK_NAME"]
c.DockerSpawner.network_name = network_name

etherpad_enabled = _env_flag("ETHERPAD_ENABLED", True)
c.DockerSpawner.environment = {
    "JUPYTERHUB_SINGLEUSER_APP": "jupyter-server",
    "TA_MIDDLEWARE_URL": os.environ.get("TA_MIDDLEWARE_URL", "http://middleware:8004"),
    "ETHERPAD_ENABLED": "true" if etherpad_enabled else "false",
    "ETHERPAD_URL": os.environ.get("ETHERPAD_INTERNAL_URL", "http://etherpad:9001"),
    "ETHERPAD_API_KEY": _read_secret("ETHERPAD_API_KEY", "ETHERPAD_API_KEY_FILE") if etherpad_enabled else "",
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
            # Shuts down servers after this many seconds of inactivity
            f"--timeout={os.environ.get('NOTEBOOK_IDLE_TIMEOUT', '1800')}",
        ],
    }
]
c.DockerSpawner.mem_limit = os.environ.get("NOTEBOOK_MEM_LIMIT", "400M")
c.DockerSpawner.cpu_limit = float(os.environ.get("NOTEBOOK_CPU_LIMIT", "0.5"))

c.DockerSpawner.stop_timeout = 30 

# --- Storage and Data Persistence ---
notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")
c.DockerSpawner.notebook_dir = notebook_dir
c.DockerSpawner.volumes = {"jupyterhub-user-{username}": notebook_dir,
                           "jupyterhub-logs-{username}": "/home/jovyan/logs/processed"}
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
# With open signup, new users can log in without approval by the admin.
c.NativeAuthenticator.open_signup = _env_flag("JUPYTERHUB_OPEN_SIGNUP", False)
admin = os.environ.get("JUPYTERHUB_ADMIN")
if admin:
    c.Authenticator.admin_users = [admin]

# Allow all signed-up users to login
c.Authenticator.allow_all = True