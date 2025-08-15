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

ROOT_PATH = os.getenv("JUPYTERHUB_SERVICE_PREFIX", "")
app = FastAPI(title="JELAI Admin Dashboard", version="0.1.0", root_path=ROOT_PATH)

# Mount static files with service prefix
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Configuration
MIDDLEWARE_URL = os.environ.get('MIDDLEWARE_URL', 'http://middleware:8005')
JUPYTERHUB_URL = os.environ.get('JUPYTERHUB_URL', 'http://hub:8000')

HUB_API_URL = os.getenv("JUPYTERHUB_API_URL", "http://jupyterhub:8080")
# OAuth client for this service (default matches JupyterHub convention)
JUPYTERHUB_CLIENT_ID = os.getenv("JUPYTERHUB_CLIENT_ID", "service-learn-dashboard")
SERVICE_TOKEN = os.getenv("JUPYTERHUB_API_TOKEN")

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
    return None

async def _user_for_token(token: str) -> Optional[dict]:
    # Introspect token by calling Hub user API with the user token
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(
            f"{HUB_API_URL}/hub/api/user",
            headers={"Authorization": f"token {token}"},
        )
    if r.status_code == 200:
        return r.json()
    return None

async def get_current_user(request: Request) -> dict:
    # Validate via OAuth access token (required since JupyterHub 2.0)
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing OAuth token")
    user = await _user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid OAuth token")
    return user  # includes name/admin/groups

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("admin", False):
        raise HTTPException(status_code=403)
    return user

@app.get("/")
async def dashboard_root(request: Request):
    """Main dashboard page (redirect to login if needed, but allow health checks)"""
    # If this is a simple GET without browser headers, treat as health check
    user_agent = request.headers.get("user-agent", "")
    if not user_agent or "curl" in user_agent.lower() or "python" in user_agent.lower():
        return {"status": "healthy", "service": "learn-dashboard"}
    
    # Normal browser request - require authentication
    token = _get_token_from_request(request)
    if not token:
        return RedirectResponse(url=f"{ROOT_PATH}/login?next={ROOT_PATH}/")
    user = await _user_for_token(token)
    if not user or not user.get("admin", False):
        raise HTTPException(status_code=403)
    return templates.TemplateResponse("dashboard.html", {"request": request})

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
async def proxy_to_middleware(request: Request, endpoint: str, user=Depends(require_admin)):
    """Proxy requests to middleware admin API"""
    try:
        url = f"{MIDDLEWARE_URL}/api/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            if request.method == "GET":
                response = await client.get(url)
            elif request.method == "POST":
                content_type = request.headers.get("content-type", "")
                
                if "application/json" in content_type:
                    body = await request.json()
                    response = await client.post(url, json=body)
                elif "multipart/form-data" in content_type:
                    # Handle file uploads with proper filename preservation
                    form = await request.form()
                    files = {}
                    for field_name, file_data in form.items():
                        if hasattr(file_data, 'filename'):
                            files[field_name] = (file_data.filename, file_data.file, file_data.content_type)
                    response = await client.post(url, files=files)
                else:
                    body = await request.body()
                    response = await client.post(url, content=body)
            elif request.method == "PUT":
                body = await request.json()
                response = await client.put(url, json=body)
            elif request.method == "DELETE":
                response = await client.delete(url)
        
        return JSONResponse(content=response.json(), status_code=response.status_code)
    except Exception as e:
        logger.error(f"Error proxying request to {url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user")
async def get_user(user=Depends(get_current_user)):
    """Get current user info"""
    return {"name": user.get("name"), "admin": user.get("admin", False)}

if __name__ == '__main__':
    logger.info("Starting JELAI Admin Dashboard on port 8006")
    uvicorn.run(app, host="0.0.0.0", port=8006)
