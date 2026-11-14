#!/usr/bin/env bash
# Install JELAI on a new Ubuntu or Debian server and start it.
#
# Run as root on the server:
#   curl -fsSL https://raw.githubusercontent.com/mvallet91/JELAI/main/deploy/vm-setup.sh -o vm-setup.sh
#   LLM_PROVIDER=groq LLM_API_KEY=... bash vm-setup.sh
#
# Settings (environment variables, all optional except the LLM settings):
#   LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL   the LLM (see docs/llm-providers.md)
#   TEACHER_PASSWORD         password of the teacher pages (default: a random one)
#   JUPYTERHUB_ADMIN         user name of the admin (default: admin)
#   JUPYTERHUB_OPEN_SIGNUP   true: students sign up without approval (default: false)
#   NOTEBOOK_MEM_LIMIT       memory of each student notebook (default: 768M)
#   TEACHER_PUBLIC           true: the teacher pages are open on the public port 8004.
#                            Default false: only the server itself can open them
#                            (use an SSH tunnel, see docs/deploy-vm.md).
#   JELAI_DOMAIN             host name for HTTPS, for example jelai.example.org. It needs
#                            a DNS A record to this server. Without it, JELAI uses HTTP.
#   TEACHER_DOMAIN           host name of the teacher pages with HTTPS (optional)
#   ETHERPAD_DOMAIN          host name of Etherpad with HTTPS (optional)
#   REPO_URL, BRANCH         the source of JELAI (default: the main branch on GitHub)
#   INSTALL_DIR              the directory on the server (default: /opt/jelai)

set -euo pipefail

if [[ $EUID -ne 0 ]]; then
    echo "Run this script as root (for example: sudo bash vm-setup.sh)." >&2
    exit 1
fi

REPO_URL="${REPO_URL:-https://github.com/mvallet91/JELAI.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/jelai}"

if [[ -z "${LLM_PROVIDER:-}" ]]; then
    echo "Set LLM_PROVIDER (and LLM_API_KEY) before you run this script. See docs/llm-providers.md." >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# Swap protects a small server when the memory is full.
if [[ -z "$(swapon --show --noheadings)" ]]; then
    echo "Making 2 GB of swap."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile >/dev/null
    swapon /swapfile
    grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

if ! command -v git >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
    apt-get update -y
    apt-get install -y git curl ca-certificates openssl
fi

if ! command -v docker >/dev/null 2>&1; then
    echo "Installing Docker."
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

if [[ -d "$INSTALL_DIR/.git" ]]; then
    git -C "$INSTALL_DIR" fetch origin "$BRANCH"
    git -C "$INSTALL_DIR" checkout "$BRANCH"
    git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
    git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

./setup.sh --yes

ENV_FILE="$INSTALL_DIR/jupyterhub-docker/.env"
set_var() {
    if grep -q "^$1=" "$ENV_FILE"; then
        sed -i "s|^$1=.*|$1=$2|" "$ENV_FILE"
    else
        echo "$1=$2" >> "$ENV_FILE"
    fi
}
set_var JUPYTERHUB_OPEN_SIGNUP "${JUPYTERHUB_OPEN_SIGNUP:-false}"
set_var NOTEBOOK_MEM_LIMIT "${NOTEBOOK_MEM_LIMIT:-768M}"
if [[ "${TEACHER_PUBLIC:-false}" != "true" ]]; then
    set_var TEACHER_DASHBOARD_PORT "127.0.0.1:8004"
fi
if [[ -n "${JELAI_DOMAIN:-}" ]]; then
    # With HTTPS, Caddy is the only door: the HTTP ports stay on the server.
    profiles="$(grep '^COMPOSE_PROFILES=' "$ENV_FILE" | cut -d= -f2-)"
    [[ ",$profiles," == *",https,"* ]] || set_var COMPOSE_PROFILES "${profiles:+$profiles,}https"
    set_var JELAI_DOMAIN "$JELAI_DOMAIN"
    set_var TEACHER_DOMAIN "${TEACHER_DOMAIN:-}"
    set_var ETHERPAD_DOMAIN "${ETHERPAD_DOMAIN:-}"
    set_var JUPYTERHUB_PORT "127.0.0.1:8000"
    set_var TEACHER_DASHBOARD_PORT "127.0.0.1:8004"
    set_var ETHERPAD_PORT "127.0.0.1:9001"
fi

cd jupyterhub-docker
docker compose build
docker compose up -d

ip="$(curl -fsS -m 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
password="$(grep '^TEACHER_PASSWORD=' "$ENV_FILE" | cut -d= -f2-)"
admin="$(grep '^JUPYTERHUB_ADMIN=' "$ENV_FILE" | cut -d= -f2-)"
echo
echo "JELAI is running."
if [[ -n "${JELAI_DOMAIN:-}" ]]; then
    echo "  Students:         https://$JELAI_DOMAIN   (sign up as '${admin:-admin}' first)"
else
    echo "  Students:         http://$ip:8000   (sign up as '${admin:-admin}' first)"
fi
if [[ -n "${JELAI_DOMAIN:-}" && -n "${TEACHER_DOMAIN:-}" ]]; then
    echo "  Teacher settings: https://$TEACHER_DOMAIN/teacher-settings"
elif [[ "${TEACHER_PUBLIC:-false}" == "true" ]]; then
    echo "  Teacher settings: http://$ip:8004/teacher-settings"
else
    echo "  Teacher settings: ssh -L 8004:localhost:8004 root@$ip, then http://localhost:8004/teacher-settings"
fi
echo "  Teacher user:     teacher"
echo "  Teacher password: $password"
if [[ -n "${JELAI_DOMAIN:-}" ]]; then
    echo "Open ports 80 and 443 in the firewall of the server."
else
    echo "Open port 8000 in the firewall of the server (and 8004 if TEACHER_PUBLIC=true)."
fi
