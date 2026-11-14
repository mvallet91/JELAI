#!/usr/bin/env bash
# Reset the demo: one student starts again from a clean copy of the course.
#
# Run as root on the server:
#   bash /opt/jelai/deploy/demo-reset.sh [student]     (default: demo-student)
#
# For this student, the script removes:
#   - the notebook server and the work folder (the next login copies the
#     course materials again and opens the start notebook)
#   - the chat history, the learner data and the activity logs that the
#     teacher dashboard shows
#   - the Etherpad pad of the student
# It also puts agent_config.yaml back to the version in Git, so hints that
# were changed during the demo are gone (a copy is kept as
# agent_config.yaml.before-reset).
#
# It keeps the accounts and passwords, the course materials, the start
# notebook, the other input files and the HTTPS certificates.
#
# Settings: INSTALL_DIR (default /opt/jelai).

set -euo pipefail

STUDENT="${1:-demo-student}"
INSTALL_DIR="${INSTALL_DIR:-/opt/jelai}"
COMPOSE_DIR="$INSTALL_DIR/jupyterhub-docker"
INPUTS="$COMPOSE_DIR/middleware/inputs"

if [[ $EUID -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi
if [[ ! "$STUDENT" =~ ^[A-Za-z0-9._@-]+$ ]]; then
    echo "This is not a valid user name: $STUDENT" >&2
    exit 1
fi

# DockerSpawner escapes the user name in container and volume names
# ("demo-student" becomes "demo-2dstudent").
escaped="$(docker exec jupyterhub python3 -c \
    'import sys; from dockerspawner import DockerSpawner; print(DockerSpawner._escape(sys.argv[1]))' \
    "$STUDENT" 2>/dev/null || true)"
if [[ -z "$escaped" ]]; then
    escaped="$(python3 -c 'import sys
from string import ascii_lowercase, digits
safe = set(ascii_lowercase + digits)
print("".join(c if c in safe else "-%02x" % ord(c) for c in sys.argv[1]))' "$STUDENT")"
fi

echo "Resetting the demo for $STUDENT."

# 1. Notebook server and work folder
docker rm -f "jupyter-$escaped" >/dev/null 2>&1 && echo "  removed the notebook server" || true
for volume in "jupyterhub-user-$escaped" "jupyterhub-logs-$escaped"; do
    docker volume rm "$volume" >/dev/null 2>&1 && echo "  removed volume $volume" || true
done

# 2. Chat history, learner data and activity logs in the middleware
docker exec -i middleware python3 - "$STUDENT" <<'PY'
import os, sqlite3, sys
student = sys.argv[1]
db = "/app/chat_histories/chat_history.db"
if os.path.exists(db):
    con = sqlite3.connect(db)
    tables = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
    for table in ("chat_history", "student_profiles", "learner_models", "student_experiment_assignments"):
        if table in tables:
            n = con.execute(f"delete from {table} where student_id = ?", (student,)).rowcount
            print(f"  deleted {n} rows from {table}")
    con.commit()
logs_dir = os.getenv("INGESTED_LOGS_DIR", "/app/chat_histories/student_logs")
path = os.path.join(logs_dir, f"{student}.json")
if os.path.exists(path):
    os.remove(path)
    print("  removed the activity log of the dashboard")
PY

# 3. Etherpad pad of the student. The request URL holds the API key, so the
#    HTTP client must not log it.
docker exec -i middleware python3 - "$STUDENT" 2>/dev/null <<'PY' || true
import logging, sys
from learning_story import ETHERPAD_API_KEY, ETHERPAD_URL, pad_id_for
logging.disable(logging.CRITICAL)
import httpx
pad = pad_id_for(sys.argv[1])
if ETHERPAD_API_KEY:
    r = httpx.get(f"{ETHERPAD_URL}/api/1/deletePad",
                  params={"apikey": ETHERPAD_API_KEY, "padID": pad}, timeout=5.0)
    print("  removed the pad" if r.json().get("code") == 0 else "  no pad to remove")
PY

# 4. Tutor configuration from Git
if ! git -C "$INSTALL_DIR" diff --quiet -- "$INPUTS/agent_config.yaml"; then
    cp "$INPUTS/agent_config.yaml" "$INPUTS/agent_config.yaml.before-reset"
    git -C "$INSTALL_DIR" checkout -- "$INPUTS/agent_config.yaml"
    echo "  restored agent_config.yaml (old copy: agent_config.yaml.before-reset)"
fi

# 5. The middleware keeps counters in memory (for example the streak of
#    executive questions), and the hub must see that the notebook server is
#    gone. A restart of both clears this. Other notebook servers keep running.
(cd "$COMPOSE_DIR" && docker compose restart middleware hub >/dev/null 2>&1)
echo "  restarted the middleware and the hub"

echo "Done. $STUDENT can log in again and starts from the beginning."
