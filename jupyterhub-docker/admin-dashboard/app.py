#!/usr/bin/env python3
"""
JELAI Admin Dashboard - Web interface for educators to manage the system
"""

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import os
import json
import logging
from typing import List, Optional
import uvicorn
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# If a local .env file exists in this service directory, load simple KEY=VALUE pairs
# into os.environ unless already set. This makes it convenient to enable
# ALLOW_DEV_AUTH during local development without modifying docker-compose.
def _load_local_env():
    try:
        # Search in a few likely locations: service dir, parent dir, repo root, CWD
        base = os.path.dirname(__file__)
        candidates = [
            os.path.join(base, '.env'),
            os.path.join(base, '..', '.env'),
            os.path.join(base, '..', '..', '.env'),
            os.path.join(os.getcwd(), '.env'),
        ]
        found = None
        for env_path in candidates:
            env_path = os.path.abspath(env_path)
            if os.path.exists(env_path):
                found = env_path
                break
        if not found:
            return None
        with open(found, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # don't override existing environment variables
                if os.environ.get(k) is None:
                    os.environ[k] = v
        return found
    except Exception:
        logger.exception('Failed to load local .env')
    return None


# Load local .env early so subsequent os.getenv() calls can pick up overrides
local_env_path = _load_local_env()
ROOT_PATH = os.getenv("JUPYTERHUB_SERVICE_PREFIX", "")
app = FastAPI(title="JELAI Admin Dashboard", version="0.1.0", root_path=ROOT_PATH)
# Mount static files with service prefix
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Configuration
MIDDLEWARE_URL = os.getenv('MIDDLEWARE_URL', 'http://middleware:8005')
HUB_API_URL = os.getenv("JUPYTERHUB_API_URL", "http://jupyterhub:8080")
JUPYTERHUB_CLIENT_ID = os.getenv("JUPYTERHUB_CLIENT_ID", "service-learn-dashboard")
SERVICE_TOKEN = os.getenv("JUPYTERHUB_API_TOKEN")
PORT = int(os.getenv("PORT", "8006"))
# Development helper: when ALLOW_DEV_AUTH is true, the dashboard will accept
# simple username authentication for local CLI testing. Only enable this in
# development environments. Accepted forms (when enabled):
#  - HTTP header: Authorization: Bearer <username>
#  - Query param: ?user=<username>
#  - Header override: X-DEV-USER: <username>
# To mark a dev user as admin, include header: X-ADMIN: true
ALLOW_DEV_AUTH = str(os.getenv("ALLOW_DEV_AUTH", "false")).lower() in ("1", "true", "yes")

# Log dev auth state for easier debugging in development
logger.info(f"ALLOW_DEV_AUTH={ALLOW_DEV_AUTH}, LOCAL_ENV_FILE={local_env_path}, SERVICE_TOKEN_SET={'yes' if SERVICE_TOKEN else 'no'}")

@app.get('/_debug_env')
async def _debug_env():
    """Debug endpoint (safe to remove) that reports effective dev auth flags. Do not enable in production."""
    return {
        'ALLOW_DEV_AUTH': ALLOW_DEV_AUTH,
        'env_ALLOW_DEV_AUTH': os.environ.get('ALLOW_DEV_AUTH'),
        'SERVICE_TOKEN': bool(SERVICE_TOKEN),
        'ADMIN_USER': os.environ.get('ADMIN_USER', 'admin'),
        'local_env_path': local_env_path,
    }

# Validate required environment variables (allow missing service token in dev bypass)
if not SERVICE_TOKEN and not ALLOW_DEV_AUTH:
    raise RuntimeError("JUPYTERHUB_API_TOKEN environment variable is required")

TOKEN_COOKIE_NAME = "jhub_service_oauth_token"

def _get_token_from_request(request: Request) -> Optional[str]:
    # Prefer Authorization header
    authz = request.headers.get("authorization")
    if authz:
        parts = authz.split()
        if len(parts) == 2 and parts[0].lower() in ("bearer", "token"):
            return parts[1]
    # Fallback to our own cookie
    token = request.cookies.get(TOKEN_COOKIE_NAME)
    if token:
        return token
    # In development mode allow `?user=` or X-DEV-USER header containing a simple username
    if ALLOW_DEV_AUTH:
        dev_user = request.headers.get('x-dev-user')
        if dev_user:
            return dev_user
        qp_user = request.query_params.get('user')
        if qp_user:
            return qp_user
    return None

async def _user_for_token(token: str) -> Optional[dict]:
    # Introspect token by calling Hub user API with the user token
    # Development bypass: treat the token as a username when enabled
    # If dev auth is enabled, only treat very short, alphanumeric tokens as
    # developer usernames (e.g., 'teacher1'). Real Hub OAuth tokens are longer
    # and may include non-alphanumeric characters; for those we should call
    # the Hub API to resolve the token to a username.
    if ALLOW_DEV_AUTH:
        # heuristic: treat token as dev username if short and alphanumeric
        if len(token) <= 20 and token.isalnum():
            username = token
            admin_user = os.environ.get('ADMIN_USER', 'admin')
            is_admin = (username == admin_user)
            return {"name": username, "admin": is_admin}
        # else fall through to real introspection

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{HUB_API_URL}/hub/api/user",
            headers={"Authorization": f"token {token}"},
        )
    if r.status_code == 200:
        return r.json()
    return None

async def get_current_user(request: Request) -> dict:
    # First, if the request was proxied by JupyterHub it MAY include the
    # headers X-JupyterHub-User and X-JupyterHub-Admin set by the Hub proxy.
    # Trust these headers only in a proxied environment (this service runs
    # behind the Hub in production). They allow the Hub to authenticate users
    # for the service without exposing tokens.
    jhub_user = request.headers.get('x-jupyterhub-user') or request.headers.get('X-JupyterHub-User')
    jhub_admin = request.headers.get('x-jupyterhub-admin') or request.headers.get('X-JupyterHub-Admin')
    if jhub_user:
        is_admin = (str(jhub_admin).lower() == 'true') or (jhub_user == os.environ.get('ADMIN_USER', 'admin'))
        return {"name": jhub_user, "admin": is_admin}

    # Validate via OAuth access token (required since JupyterHub 2.0)
    token = _get_token_from_request(request)

    # If no token and dev auth is enabled, allow query/header-based dev user
    if not token and ALLOW_DEV_AUTH:
        dev_user = request.headers.get('x-dev-user') or request.query_params.get('user')
        if dev_user:
            admin_flag = request.headers.get('x-admin', '').lower() == 'true' or dev_user == os.environ.get('ADMIN_USER', 'admin')
            return {"name": dev_user, "admin": admin_flag}

    if not token:
        raise HTTPException(status_code=401, detail="Missing OAuth token")

    user = await _user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid OAuth token")
    # Allow overriding admin via X-ADMIN header in dev mode
    if ALLOW_DEV_AUTH and request.headers.get('x-admin', '').lower() == 'true':
        user['admin'] = True
    return user  # includes name/admin/groups

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("admin", False):
        raise HTTPException(status_code=403)
    return user

@app.get("/")
async def dashboard_root(request: Request, user: dict = Depends(get_current_user)):
    """Main dashboard page (redirect to login if needed, but allow health checks)
    Allows any authenticated user (teacher or admin) to view the dashboard; the
    template can conditionally render admin-only controls using `user['admin']`.
    """
    # If this is a simple GET without browser headers, treat as health check
    user_agent = request.headers.get("user-agent", "")
    if not user_agent or "curl" in user_agent.lower() or "python" in user_agent.lower():
        return {"status": "healthy", "service": "learn-dashboard"}

    # Authenticated users are injected via dependency; if get_current_user raises
    # it will return a 401/403 and redirect flow will be handled by the caller.
    # Render the dashboard template and include the resolved `user` so frontend
    # can show/hide admin controls.
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.get("/login")
async def login(request: Request, next: Optional[str] = None):
    """Start OAuth login by redirecting to JupyterHub authorize."""
    # Use path-only redirect URI that matches the service registration
    redirect_uri = "/services/learn-dashboard/oauth_callback"
    # Build Hub authorize URL on the same public host
    base = f"{request.url.scheme}://{request.headers.get('host')}"
    params = {
        "client_id": JUPYTERHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    if next:
        params["state"] = next
    authorize_path = "/hub/api/oauth2/authorize?" + urlencode(params)
    return RedirectResponse(url=base + authorize_path)

@app.get("/oauth_callback")
async def oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None):
    if not code:
        raise HTTPException(status_code=400, detail="Missing code")
    # Use the same path-only redirect URI for token exchange
    redirect_uri = "/services/learn-dashboard/oauth_callback"
    data = {
        "client_id": JUPYTERHUB_CLIENT_ID,
        "client_secret": SERVICE_TOKEN,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(f"{HUB_API_URL}/hub/api/oauth2/token", data=data)
    if r.status_code != 200:
        logger.error(f"OAuth token exchange failed: {r.status_code} {r.text}")
        raise HTTPException(status_code=401, detail="OAuth token exchange failed")
    token = r.json().get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No access token")
    # Set token cookie and redirect to state or root
    response = RedirectResponse(url=state or f"{ROOT_PATH}/")
    # Secure cookie flags: Hub may be behind HTTPS at the edge; set httponly
    response.set_cookie(TOKEN_COOKIE_NAME, token, httponly=True, secure=False, samesite="lax", path=ROOT_PATH or "/")
    return response

@app.get("/health")
async def health():
    """Health check endpoint (no auth required)"""
    return {"status": "healthy", "service": "learn-dashboard"}

@app.api_route("/api/proxy/{endpoint:path}", 
               methods=["GET", "POST", "PUT", "DELETE"],
               operation_id="proxy_to_middleware")
async def proxy_to_middleware(request: Request, endpoint: str, user=Depends(get_current_user)):
    """Proxy requests to middleware admin API"""
    url = f"{MIDDLEWARE_URL}/api/{endpoint}"

    # Build headers to forward to middleware. Include current username and an
    # admin indicator header so middleware can perform RBAC checks.
    proxied_headers = {}
    try:
        # If JupyterHub has forwarded the current user's username in a header
        # (e.g. X-JupyterHub-User) prefer that value so requests coming via the
        # Hub proxy preserve identity. Otherwise, use the resolved `user` name.
        jhub_user = request.headers.get('x-jupyterhub-user') or request.headers.get('X-JupyterHub-User')
        effective_user = jhub_user or user.get('name')
        proxied_headers['Authorization'] = f"Bearer {effective_user}"
    except Exception:
        pass
    # Only set X-JELAI-ADMIN if the user is truly an admin (don't force admin for teachers)
    try:
        # If the incoming request carried an explicit hub-admin header, respect it.
        jhub_admin = request.headers.get('x-jupyterhub-admin') or request.headers.get('X-JupyterHub-Admin')
        if (jhub_admin and jhub_admin.lower() == 'true') or user.get('admin') or (effective_user and effective_user == os.environ.get('ADMIN_USER', 'admin')):
            proxied_headers['X-JELAI-ADMIN'] = 'true'
    except Exception:
        pass

    logger.info(f"Proxying headers to middleware: {proxied_headers}")

    # Don't forward content-type explicitly; httpx will set it according to the
    # `json`, `data`, or `files` parameters we pass.
    content_type = request.headers.get("content-type", "")

    try:
        async with httpx.AsyncClient() as client:
            if request.method == "GET":
                response = await client.get(url, headers=proxied_headers)
            elif request.method == "POST":
                # JSON body
                if "application/json" in content_type:
                    try:
                        body = await request.json()
                    except Exception:
                        body = {}
                    response = await client.post(url, json=body, headers=proxied_headers)
                # urlencoded form (e.g., enroll uses URLSearchParams -> application/x-www-form-urlencoded)
                elif "application/x-www-form-urlencoded" in content_type:
                    form = await request.form()
                    data = {k: v for k, v in form.items() if not hasattr(v, 'filename')}
                    response = await client.post(url, data=data, headers=proxied_headers)
                # multipart/form-data (file uploads)
                elif "multipart/form-data" in content_type or "form-data" in content_type:
                    form = await request.form()
                    files = {}
                    data = {}
                    for field_name, file_data in form.items():
                        if hasattr(file_data, 'filename'):
                            files[field_name] = (file_data.filename, file_data.file, file_data.content_type)
                        else:
                            data[field_name] = file_data
                    response = await client.post(url, files=files, data=data, headers=proxied_headers)
                else:
                    body = await request.body()
                    response = await client.post(url, content=body, headers=proxied_headers)
            elif request.method == "PUT":
                try:
                    body = await request.json()
                except Exception:
                    body = {}
                response = await client.put(url, json=body, headers=proxied_headers)
            elif request.method == "DELETE":
                response = await client.delete(url, headers=proxied_headers)

        try:
            response_json = response.json()
            logger.info(f"Proxy response for {url}: status={response.status_code}, content={response_json}")
        except Exception as json_error:
            # Handle empty or non-JSON responses
            response_text = response.text
            logger.error(f"Failed to parse JSON response from {url}: {json_error}. Response text: '{response_text}', Status: {response.status_code}")
            response_json = {"error": f"Invalid response from middleware: {str(json_error)}"}

        return JSONResponse(content=response_json, status_code=response.status_code)
    except Exception as e:
        logger.error(f"Error proxying request to {url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user")
async def get_user(user=Depends(get_current_user)):
    """Get current user info"""
    return {"name": user.get("name"), "admin": user.get("admin", False)}

if __name__ == '__main__':
    logger.info(f"Starting JELAI Admin Dashboard on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
