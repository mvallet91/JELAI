# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.

# Configuration file for JupyterHub
import os

c = get_config()  # noqa: F821

# We rely on environment variables to configure JupyterHub so that we
# avoid having to rebuild the JupyterHub container every time we change a
# configuration parameter.

c.JupyterHub.port = 9000
# c.JupyterHub.bind_url = "http://localhost:9000"

# Spawn single-user servers as Docker containers
c.JupyterHub.spawner_class = "dockerspawner.DockerSpawner"

c.DockerSpawner.environment.update({"JUPYTERHUB_SINGLEUSER_APP": "jupyter-server"})

# Spawn containers from this image
c.DockerSpawner.image = os.environ["DOCKER_NOTEBOOK_IMAGE"]

# Connect containers to this Docker network
network_name = os.environ["DOCKER_NETWORK_NAME"]
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.network_name = network_name

# Allow access to the host's network
c.DockerSpawner.extra_host_config = {
    "extra_hosts": {"host.docker.internal": "host-gateway"}
}

# Explicitly set notebook directory because we'll be mounting a volume to it.
# Most `jupyter/docker-stacks` *-notebook images run the Notebook server as
# user `jovyan`, and set the notebook directory to `/home/jovyan/work`.
# We follow the same convention.
notebook_dir = os.environ.get("DOCKER_NOTEBOOK_DIR", "/home/jovyan/work")
c.DockerSpawner.notebook_dir = notebook_dir
default_notebook = os.environ.get("DEFAULT_NOTEBOOK")
if default_notebook:
    c.DockerSpawner.default_url = default_notebook + "?reset" # added reset to always open with zero files open
else:
    c.DockerSpawner.default_url =  "lab?reset" # added reset to always open with zero files open

# Mount the real user's Docker volume on the host to the notebook user's
# notebook directory in the container
c.DockerSpawner.volumes = {"jupyterhub-user-{username}": notebook_dir}

# Remove containers once they are stopped
c.DockerSpawner.remove = False

# For debugging arguments passed to spawned containers
c.DockerSpawner.debug = True

# User containers will access hub by container name on the Docker network
c.JupyterHub.hub_ip = "jupyterhub"
c.JupyterHub.hub_port = 8080

# Persist hub data on volume mounted inside container
c.JupyterHub.cookie_secret_file = "/data/jupyterhub_cookie_secret"
c.JupyterHub.db_url = "sqlite:////data/jupyterhub.sqlite"

# Allow all signed-up users to login
c.Authenticator.allow_all = True

# Authenticate users with Native Authenticator
c.JupyterHub.authenticator_class = "nativeauthenticator.NativeAuthenticator"

# Allow anyone to sign-up without approval
c.NativeAuthenticator.open_signup = False

# Allowed admins
admin = os.environ.get("JUPYTERHUB_ADMIN")
if admin:
    c.Authenticator.admin_users = [admin]

# Limit resources per-user
c.Spawner.mem_limit = "400M"
c.Spawner.cpu_limit = 0.5
c.Spawner.stop_timeout = 30
c.Spawner.idle_timeout = 60