#!/usr/bin/env bash
# JELAI setup: makes jupyterhub-docker/.env and the Etherpad API key.
#
# Usage:
#   ./setup.sh            ask the questions
#   ./setup.sh --yes      use the defaults and the environment variables
#                         (LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL,
#                         TEACHER_PASSWORD, JUPYTERHUB_ADMIN) without questions
#
# Then:
#   cd jupyterhub-docker && docker compose build && docker compose up -d

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STACK="$ROOT/jupyterhub-docker"
ENV_FILE="$STACK/.env"
EXAMPLE="$STACK/.env.example"
APIKEY_FILE="$STACK/etherpad/APIKEY.txt"

ASSUME_YES=false
if [[ "${1:-}" == "--yes" || "${1:-}" == "-y" ]]; then
    ASSUME_YES=true
fi

random_secret() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex "${1:-16}"
    else
        head -c "${1:-16}" /dev/urandom | od -An -tx1 | tr -d ' \n'
    fi
}

ask() {
    # ask <question> <default> -> prints the answer
    local question="$1" default="${2:-}" answer
    if $ASSUME_YES; then
        printf '%s' "$default"
        return
    fi
    if [[ -n "$default" ]]; then
        read -r -p "$question [$default]: " answer
    else
        read -r -p "$question: " answer
    fi
    printf '%s' "${answer:-$default}"
}

ask_secret() {
    local question="$1" default="${2:-}" answer
    if $ASSUME_YES; then
        printf '%s' "$default"
        return
    fi
    read -r -s -p "$question${default:+ [keep current]}: " answer
    echo >&2
    printf '%s' "${answer:-$default}"
}

set_var() {
    # set_var <name> <value>: replace or add NAME=value in .env
    local name="$1" value="$2" tmp
    tmp="$(mktemp)"
    awk -v name="$name" -v value="$value" '
        BEGIN { done = 0 }
        $0 ~ "^" name "=" { print name "=" value; done = 1; next }
        { print }
        END { if (!done) print name "=" value }
    ' "$ENV_FILE" > "$tmp"
    mv "$tmp" "$ENV_FILE"
}

get_var() {
    [[ -f "$ENV_FILE" ]] || return 0
    grep -E "^$1=" "$ENV_FILE" | tail -n1 | cut -d= -f2- || true
}

echo "== JELAI setup =="

if [[ -f "$ENV_FILE" ]]; then
    echo "Found $ENV_FILE. The script keeps your values as defaults."
    cp "$ENV_FILE" "$ENV_FILE.bak"
else
    cp "$EXAMPLE" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

current_provider="${LLM_PROVIDER:-$(get_var LLM_PROVIDER)}"
if ! $ASSUME_YES; then
    cat <<'EOF'

Which LLM provider do you want to use?
  ollama        Self-hosted Ollama server (no API key, needs a GPU server)
  openai        OpenAI API (paid)
  openwebui     Open WebUI server of your school or university (URL + API key)
  groq          Groq: free tier, no credit card
  gemini        Google Gemini: free tier (outside the EU/UK only, see README)
  mistral       Mistral AI: free monthly credits, servers in the EU
  openrouter    OpenRouter: free models (set the model name)
  ollama-cloud  Ollama Cloud: free tier
  custom        Another OpenAI-compatible server
EOF
fi
provider="$(ask "Provider" "${current_provider:-ollama}")"
set_var LLM_PROVIDER "$provider"

default_url="${LLM_BASE_URL:-$(get_var LLM_BASE_URL)}"
case "$provider" in
    ollama)
        base_url="$(ask "Ollama URL (with /v1)" "${default_url:-http://host.docker.internal:11434/v1}")" ;;
    openwebui)
        base_url="$(ask "Open WebUI server URL (for example https://chat.example.org)" "$default_url")" ;;
    custom)
        base_url="$(ask "API base URL (for example https://llm.example.org/v1)" "$default_url")" ;;
    *)
        base_url="$(ask "API base URL (empty: default of the provider)" "$default_url")" ;;
esac
set_var LLM_BASE_URL "$base_url"

if [[ "$provider" != "ollama" ]]; then
    api_key="$(ask_secret "API key" "${LLM_API_KEY:-$(get_var LLM_API_KEY)}")"
    set_var LLM_API_KEY "$api_key"
fi

model_default="${LLM_MODEL:-$(get_var LLM_MODEL)}"
if [[ "$provider" == "openrouter" && -z "$model_default" ]]; then
    echo "OpenRouter: see https://openrouter.ai/models?max_price=0 for model names that end in ':free'." >&2
fi
model="$(ask "Model (empty: default of the provider)" "$model_default")"
set_var LLM_MODEL "$model"

admin="$(ask "JupyterHub admin user name" "${JUPYTERHUB_ADMIN:-$(get_var JUPYTERHUB_ADMIN)}")"
set_var JUPYTERHUB_ADMIN "${admin:-admin}"

teacher_password="${TEACHER_PASSWORD:-$(get_var TEACHER_PASSWORD)}"
generated_password=false
if [[ -z "$teacher_password" ]]; then
    teacher_password="$(random_secret 9)"
    generated_password=true
fi
if ! $ASSUME_YES; then
    answer="$(ask_secret "Teacher dashboard password (empty: keep or generate)" "")"
    if [[ -n "$answer" ]]; then
        teacher_password="$answer"
        generated_password=false
    fi
fi
set_var TEACHER_PASSWORD "$teacher_password"

mkdir -p "$STACK/etherpad" "$STACK/course_materials"

# The hub gives this folder to the student notebooks. Docker needs the
# absolute path on the host. In Git Bash on Windows, "pwd -W" gives C:/...
if materials_dir="$(cd "$STACK/course_materials" && pwd -W 2>/dev/null)"; then :; else
    materials_dir="$(cd "$STACK/course_materials" && pwd)"
fi
set_var COURSE_MATERIALS_DIR "$materials_dir"
if [[ -d "$APIKEY_FILE" ]]; then
    # Docker makes a directory when it mounts a file that does not exist.
    rmdir "$APIKEY_FILE" 2>/dev/null || true
fi
if [[ ! -s "$APIKEY_FILE" ]]; then
    random_secret 32 > "$APIKEY_FILE"
    echo "Made a new Etherpad API key in $APIKEY_FILE."
fi
chmod 644 "$APIKEY_FILE"

port="$(get_var JUPYTERHUB_PORT)"
dashboard_port="$(get_var TEACHER_DASHBOARD_PORT)"
echo
echo "Saved $ENV_FILE."
echo
echo "Next steps:"
echo "  cd jupyterhub-docker"
echo "  docker compose build"
echo "  docker compose up -d"
echo
echo "JupyterHub:        http://localhost:${port:-8000}  (sign up as '${admin:-admin}' first)"
echo "Teacher dashboard: http://localhost:${dashboard_port:-8004}/teacher-view  (user 'teacher')"
if $generated_password; then
    echo "Teacher password:  $teacher_password  (also in $ENV_FILE)"
fi
