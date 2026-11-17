#!/usr/bin/env bash
# Update the server to the latest commit of the branch that is checked out.
#
# Run as root on the server:
#   bash /opt/jelai/deploy/update.sh
#
# The script:
#   1. gets the new commits (git pull --ff-only, no merge)
#   2. builds the images again (Docker uses the cache, so only the changed
#      images take time)
#   3. starts the containers again that have a new image or configuration
# It does not change the .env file, the accounts, the student work or the
# made-up students of demo-seed.sh.
#
# Settings: INSTALL_DIR (default /opt/jelai).

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/jelai}"
COMPOSE_DIR="$INSTALL_DIR/jupyterhub-docker"

if [[ $EUID -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi

cd "$INSTALL_DIR"

# git pull can change this script. Bash reads a script while it runs it, so
# run the new version of the script after the pull.
if [[ "${JELAI_UPDATE_PULLED:-}" != "1" ]]; then
    if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
        echo "There are local changes in $INSTALL_DIR. Commit or remove them first:" >&2
        git status --short --untracked-files=no >&2
        exit 1
    fi
    before="$(git rev-parse --short HEAD)"
    git pull --ff-only --quiet
    echo "Branch $(git branch --show-current): $before -> $(git rev-parse --short HEAD)"
    JELAI_UPDATE_PULLED=1 exec bash "$INSTALL_DIR/deploy/update.sh" "$@"
fi

cd "$COMPOSE_DIR"
docker compose build --quiet
docker compose up -d

# Health check: wait until the middleware is healthy (at most 90 seconds).
status=""
for _ in $(seq 1 30); do
    status="$(docker inspect --format '{{.State.Health.Status}}' middleware 2>/dev/null || true)"
    [[ "$status" == "healthy" ]] && break
    sleep 3
done
docker compose ps --format '{{.Name}}: {{.Status}}'
if [[ "$status" != "healthy" ]]; then
    echo "The middleware is not healthy (status: ${status:-unknown}). See: docker compose logs middleware" >&2
    exit 1
fi
echo "Update complete: $(git -C "$INSTALL_DIR" rev-parse --short HEAD)"
