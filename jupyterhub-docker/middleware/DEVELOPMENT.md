Development notes — in-place iteration vs rebuild

Goal
----
Document the fast "in-place" workflow (what we used in the container) and the steps required to make those changes persistent in an image rebuild.

What we changed during iteration
- Added `__init__.py` to make the middleware a package.
- Added `setup.cfg` / `pyproject.toml` so the project can be installed editable (`pip install -e /app`).
- Edited `admin_api.py` (role-filtered `/api/courses`) and `tests/conftest.py` to make tests import robust.

Quick in-place iteration (fast, used for dev)
1. Copy updated files from host into the running middleware container:

```bash
# run from repo root in WSL
CONTAINER=<middleware_container_name_or_id>
# copy tests and packaging files
docker cp jupyterhub-docker/tests/. $CONTAINER:/app/tests
docker cp jupyterhub-docker/middleware/pyproject.toml $CONTAINER:/app/pyproject.toml
docker cp jupyterhub-docker/middleware/setup.cfg $CONTAINER:/app/setup.cfg
docker cp jupyterhub-docker/middleware/__init__.py $CONTAINER:/app/__init__.py
# copy updated source files (e.g. admin_api.py, courses.py)
docker cp jupyterhub-docker/middleware/admin_api.py $CONTAINER:/app/admin_api.py
docker cp jupyterhub-docker/middleware/courses.py $CONTAINER:/app/courses.py
```

2. Install editable and run tests inside container:

```bash
# inside host shell
docker exec -u root $CONTAINER bash -lc "pip install -e /app || true && pip install pytest || true && pytest -q /app/tests || true"
```

Notes
- This in-place approach is fast for iteration, but it mutates the running container only — these changes will be lost if the container is recreated from the image.
- Keep a short record of exact commands you run (this file) so you can reproduce them before a rebuild.

Making changes persistent (rebuild)
1. Ensure packaging files are committed to the repo (`pyproject.toml`, `setup.cfg`, `middleware/__init__.py`).
2. Ensure the Dockerfile in this directory copies the packaging files (the current Dockerfile already copies `pyproject.toml`). If you want `pip install -e /app` during build, add a build step to install editable there (not recommended for production but useful for dev images).
3. Rebuild and restart the service:

```bash
cd jupyterhub-docker
# rebuild the middleware image
docker compose build middleware
# restart middleware
docker compose up -d middleware
# run tests inside the freshly built container
CONTAINER=$(docker compose ps -q middleware)
docker exec -u root $CONTAINER bash -lc "pytest -q /app/tests || true"
```

Recommended diff for Dockerfile (optional): to make editable installs automatic in a dev image, add after copying app files:

```dockerfile
# (dev-only) install editable local package
RUN pip install -e /app
```

Keep CI using the canonical build (not editable install) for reproducibility.

Why tracking this matters
- The in-place approach is excellent for fast iteration, but you must include the same steps or the same packaging files in your Docker build so CI/rebuilds reflect the working state.
- This file documents exactly what we ran so the next rebuild step can reproduce the same environment.

