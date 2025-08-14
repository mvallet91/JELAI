#!/usr/bin/env python3
"""
JELAI Admin Dashboard - Web interface for educators to manage the system
"""

from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx
import os
import json
import logging
from typing import List, Optional
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JELAI Admin Dashboard", version="0.1.0")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# Configuration
MIDDLEWARE_URL = os.environ.get('MIDDLEWARE_URL', 'http://middleware:8005')
JUPYTERHUB_URL = os.environ.get('JUPYTERHUB_URL', 'http://hub:8000')

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.api_route("/api/proxy/{endpoint:path}", 
               methods=["GET", "POST", "PUT", "DELETE"],
               operation_id="proxy_to_middleware")
async def proxy_to_middleware(request: Request, endpoint: str):
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

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "admin-dashboard"}

@app.get("/api/user")
async def get_user():
    """Get current user info"""
    return {"username": "admin"}

if __name__ == '__main__':
    logger.info("Starting JELAI Admin Dashboard on port 8006")
    uvicorn.run(app, host="0.0.0.0", port=8006)
