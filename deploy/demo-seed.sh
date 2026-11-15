#!/usr/bin/env bash
# Add made-up students to the demo, so the teacher dashboard shows a class.
#
# Run as root on the server:
#   bash /opt/jelai/deploy/demo-seed.sh          add eight made-up students
#   bash /opt/jelai/deploy/demo-seed.sh remove   remove them again
#
# The students, their chat messages, activity logs and pads are in
# deploy/demo_seed.py. The times are relative to now, so run the script
# again shortly before a demo. The real demo account (demo-student) is not
# changed, and demo-reset.sh does not remove the made-up students.
#
# Settings: INSTALL_DIR (default /opt/jelai).

set -euo pipefail

ACTION="${1:-add}"
INSTALL_DIR="${INSTALL_DIR:-/opt/jelai}"

if [[ $EUID -ne 0 ]]; then
    echo "Run this script as root." >&2
    exit 1
fi
if [[ "$ACTION" != "add" && "$ACTION" != "remove" ]]; then
    echo "Use: demo-seed.sh [add|remove]" >&2
    exit 1
fi

docker exec -i middleware python3 - "$ACTION" < "$INSTALL_DIR/deploy/demo_seed.py"
