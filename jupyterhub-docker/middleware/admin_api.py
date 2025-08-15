#!/usr/bin/env python3
"""
Admin API for JELAI - Pure backend API service for admin dashboard
"""

from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
import json
import sqlite3
from datetime import datetime
import shutil

# Initialize FastAPI app
app = FastAPI(title="JELAI Admin API", version="1.0.0")

# Configuration
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB
INPUTS_DIR = "/app/inputs"
LEARNING_OBJECTIVES_DIR = "/app/inputs/learning_objectives"

# Helper functions for prompt management
async def get_prompt_content(prompt_type: str) -> dict:
    """Get a system prompt by type from file system"""
    try:
        # Map prompt types to file names
        prompt_mapping = {
            "tutor": "ta_system_prompt.txt",
            "expert": "ea_system_prompt.txt"
        }
        
        if prompt_type not in prompt_mapping:
            raise HTTPException(status_code=400, detail=f"Invalid prompt type: {prompt_type}")
        
        filename = prompt_mapping[prompt_type]
        filepath = os.path.join(INPUTS_DIR, filename)
        
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                content = f.read()
            return {"content": content}
        else:
            return {"content": ""}
    except Exception as e:
        print(f"Error loading prompt {prompt_type}: {e}")
        raise HTTPException(status_code=500, detail="Error loading prompt")

async def update_prompt_content(prompt_type: str, content: str) -> dict:
    """Update a system prompt by type"""
    try:
        # Map prompt types to file names
        prompt_mapping = {
            "tutor": "ta_system_prompt.txt",
            "expert": "ea_system_prompt.txt"
        }
        
        if prompt_type not in prompt_mapping:
            raise HTTPException(status_code=400, detail=f"Invalid prompt type: {prompt_type}")
        
        filename = prompt_mapping[prompt_type]
        filepath = os.path.join(INPUTS_DIR, filename)
        
        # Ensure directory exists
        os.makedirs(INPUTS_DIR, exist_ok=True)
        
        with open(filepath, 'w') as f:
            f.write(content)
        
        return {"success": True, "message": f"Prompt '{prompt_type}' updated successfully", "content": content}
    except Exception as e:
        print(f"Error updating prompt {prompt_type}: {e}")
        raise HTTPException(status_code=500, detail="Error updating prompt")

# Base paths
INPUTS_DIR = '/app/inputs'
MATERIALS_DIR = '/app/learning_materials'
WORKSPACE_TEMPLATES_DIR = '/app/workspace_templates'
SHARED_RESOURCES_DIR = '/app/shared_resources'
CHAT_DB_PATH = '/app/chat_histories/chat_history.db'
BUILD_STATUS_FILE = '/app/logs/build_status.txt'

# Ensure directories exist
os.makedirs(INPUTS_DIR, exist_ok=True)
os.makedirs(f"{INPUTS_DIR}/learning_objectives", exist_ok=True)
os.makedirs(MATERIALS_DIR, exist_ok=True)
os.makedirs(WORKSPACE_TEMPLATES_DIR, exist_ok=True)
os.makedirs(SHARED_RESOURCES_DIR, exist_ok=True)
os.makedirs(LEARNING_OBJECTIVES_DIR, exist_ok=True)
os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)
os.makedirs(os.path.dirname(BUILD_STATUS_FILE), exist_ok=True)

# Pydantic models
class PromptRequest(BaseModel):
    content: str

class PromptResponse(BaseModel):
    content: str

class SuccessResponse(BaseModel):
    success: bool
    message: Optional[str] = None

class ErrorResponse(BaseModel):
    error: str

class FileInfo(BaseModel):
    name: str
    size: int
    modified: str

class FileListResponse(BaseModel):
    files: List[FileInfo]

class StudentAnalytics(BaseModel):
    username: str
    message_count: int
    first_interaction: str
    last_interaction: str

# Utility functions
def secure_filename(filename: str) -> str:
    """Secure a filename by removing problematic characters"""
    import re
    filename = re.sub(r'[^a-zA-Z0-9._-]', '', filename)
    return filename[:255]  # Limit length

def safe_join(directory: str, filename: str) -> str:
    """Safely join directory and filename, preventing path traversal"""
    filename = secure_filename(filename)
    path = os.path.join(directory, filename)
    if not os.path.abspath(path).startswith(os.path.abspath(directory)):
        raise ValueError("Invalid file path")
    return path

def get_file_info(directory: str) -> List[FileInfo]:
    """Get file information for all files in a directory"""
    files = []
    if os.path.exists(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append(FileInfo(
                    name=filename,
                    size=stat.st_size,
                    modified=datetime.fromtimestamp(stat.st_mtime).isoformat()
                ))
    return files

# Health check endpoint
@app.get("/")
@app.get("/health")
async def health_check():
    """API health check - dashboard UI is handled by separate service"""
    return {
        "status": "healthy",
        "service": "admin-api", 
        "message": "Dashboard UI available at /services/learn-dashboard/",
        "timestamp": datetime.now().isoformat()
    }

# AI Prompt endpoints
@app.get("/api/prompts/{prompt_type}")
async def get_prompt_api(prompt_type: str) -> dict:
    """Get a system prompt by type"""
    return await get_prompt_content(prompt_type)

@app.put("/api/prompts/{prompt_type}")
async def update_prompt_api(prompt_type: str, request: Request) -> dict:
    """Update a system prompt"""
    content_type = request.headers.get("content-type", "")
    
    if "application/json" in content_type:
        data = await request.json()
        content = data.get("content", "")
    else:
        body = await request.body()
        content = body.decode("utf-8")
    
    return await update_prompt_content(prompt_type, content)

# Legacy endpoints for backward compatibility
@app.get("/get-prompt")
async def get_prompt_legacy(prompt_type: str) -> dict:
    """Legacy get prompt endpoint"""
    return await get_prompt_content(prompt_type)

@app.post("/update-prompt")
async def update_prompt_legacy(prompt_type: str = Form(...), content: str = Form(...)) -> dict:
    """Legacy update prompt endpoint"""
    return await update_prompt_content(prompt_type, content)

# Learning Objectives endpoints
@app.get("/api/learning-objectives")
async def get_all_learning_objectives() -> Dict[str, str]:
    """Get all learning objectives"""
    try:
        objectives = {}
        if os.path.exists(LEARNING_OBJECTIVES_DIR):
            for filename in os.listdir(LEARNING_OBJECTIVES_DIR):
                if filename.endswith('.txt'):
                    task_name = filename[:-4]  # Remove .txt extension
                    filepath = os.path.join(LEARNING_OBJECTIVES_DIR, filename)
                    with open(filepath, 'r') as f:
                        objectives[task_name] = f.read()
        return objectives
    except Exception as e:
        print(f"Error loading objectives: {e}")
        raise HTTPException(status_code=500, detail="Error loading objectives")

@app.get("/api/learning-objectives/{task_name}")
async def get_learning_objectives(task_name: str):
    """Get learning objectives for specific task"""
    safe_task_name = secure_filename(task_name)
    objectives_file = os.path.join(LEARNING_OBJECTIVES_DIR, f'{safe_task_name}.txt')
    
    try:
        with open(objectives_file, 'r') as f:
            return PromptResponse(content=f.read())
    except FileNotFoundError:
        return PromptResponse(content='')

@app.put("/api/learning-objectives/{task_name}")
async def update_learning_objectives(task_name: str, request: PromptRequest):
    """Update learning objectives for specific task"""
    safe_task_name = secure_filename(task_name)
    objectives_file = os.path.join(LEARNING_OBJECTIVES_DIR, f'{safe_task_name}.txt')
    
    try:
        with open(objectives_file, 'w') as f:
            f.write(request.content)
        return SuccessResponse(success=True, message=f"Objectives saved for {task_name}")
    except Exception as e:
        print(f"Error saving objectives: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reload-learning-objectives")
@app.post("/api/reload-learning-objectives")
async def reload_learning_objectives():
    """Reload learning objectives (compatibility endpoint)"""
    try:
        count = 0
        if os.path.exists(LEARNING_OBJECTIVES_DIR):
            for filename in os.listdir(LEARNING_OBJECTIVES_DIR):
                if filename.endswith('.txt'):
                    count += 1
        
        return {
            "status": "success",
            "message": f"Learning objectives reloaded successfully ({count} files found)"
        }
    except Exception as e:
        print(f"Error reloading objectives: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Learning Materials endpoints
@app.get("/api/materials")
async def get_materials():
    """Get list of uploaded learning materials"""
    try:
        files = get_file_info(MATERIALS_DIR)
        return FileListResponse(files=files)
    except Exception as e:
        print(f"Error listing materials: {e}")
        raise HTTPException(status_code=500, detail="Error listing materials")

@app.post("/api/materials")
async def upload_material(file: UploadFile = File(...)):
    """Upload learning material file"""
    if file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    filename = secure_filename(file.filename)
    file_path = safe_join(MATERIALS_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return SuccessResponse(success=True, message=f"File uploaded: {filename}")
    except Exception as e:
        print(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Experiment Configuration endpoints
@app.get("/api/experiments")
async def get_experiments():
    """Get experiment configuration"""
    experiments_file = '/app/experiments.json'
    try:
        with open(experiments_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

@app.put("/api/experiments")
async def update_experiments(experiments: dict):
    """Update experiment configuration"""
    experiments_file = '/app/experiments.json'
    try:
        with open(experiments_file, 'w') as f:
            json.dump(experiments, f, indent=2)
        return SuccessResponse(success=True, message="Experiments updated")
    except Exception as e:
        print(f"Error saving experiments: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Student Analytics endpoints
@app.get("/api/analytics/students")
async def get_student_analytics():
    """Get student activity analytics"""
    try:
        if not os.path.exists(CHAT_DB_PATH):
            return []
        
        conn = sqlite3.connect(CHAT_DB_PATH)
        query = """
        SELECT 
            student_id as username,
            COUNT(*) as message_count,
            MIN(timestamp) as first_interaction,
            MAX(timestamp) as last_interaction
        FROM chat_history 
        GROUP BY student_id 
        ORDER BY message_count DESC
        """
        
        cursor = conn.execute(query)
        results = []
        for row in cursor:
            results.append({
                "username": row[0],
                "message_count": row[1], 
                "first_interaction": row[2],
                "last_interaction": row[3]
            })
        conn.close()
        
        return results
        
    except Exception as e:
        print(f"Error loading analytics: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error loading analytics: {str(e)}")

@app.get("/api/analytics/build-status")
async def get_build_status():
    """Get container build status"""
    try:
        with open(BUILD_STATUS_FILE, 'r') as f:
            return {"status": f.read().strip()}
    except FileNotFoundError:
        return {"status": "No build information available"}

@app.get("/api/materials/{filename}")
async def download_material(filename: str):
    """Download a learning material file"""
    try:
        file_path = safe_join(MATERIALS_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(file_path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")

# Workspace Templates endpoints
@app.get("/api/workspace-templates")
async def get_workspace_templates():
    """Get list of workspace template files"""
    try:
        files = get_file_info(WORKSPACE_TEMPLATES_DIR)
        return FileListResponse(files=files)
    except Exception as e:
        print(f"Error listing workspace templates: {e}")
        raise HTTPException(status_code=500, detail="Error listing workspace templates")

@app.post("/api/workspace-templates")
async def upload_workspace_template(file: UploadFile = File(...)):
    """Upload workspace template file"""
    if file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    filename = secure_filename(file.filename)
    file_path = safe_join(WORKSPACE_TEMPLATES_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return SuccessResponse(success=True, message=f"Template uploaded: {filename}")
    except Exception as e:
        print(f"Error uploading template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/workspace-templates/{filename}")
async def delete_workspace_template(filename: str):
    """Delete workspace template file"""
    try:
        file_path = safe_join(WORKSPACE_TEMPLATES_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        os.remove(file_path)
        return SuccessResponse(success=True, message=f"Template deleted: {filename}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    except Exception as e:
        print(f"Error deleting template: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Shared Resources endpoints  
@app.get("/api/shared-resources")
async def get_shared_resources():
    """Get list of shared resource files"""
    try:
        files = get_file_info(SHARED_RESOURCES_DIR)
        return FileListResponse(files=files)
    except Exception as e:
        print(f"Error listing shared resources: {e}")
        raise HTTPException(status_code=500, detail="Error listing shared resources")

@app.post("/api/shared-resources")
async def upload_shared_resource(file: UploadFile = File(...)):
    """Upload shared resource file"""
    if file.size > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    
    filename = secure_filename(file.filename)
    file_path = safe_join(SHARED_RESOURCES_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        return SuccessResponse(success=True, message=f"Resource uploaded: {filename}")
    except Exception as e:
        print(f"Error uploading resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/shared-resources/{filename}")
async def delete_shared_resource(filename: str):
    """Delete shared resource file"""
    try:
        file_path = safe_join(SHARED_RESOURCES_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
        os.remove(file_path)
        return SuccessResponse(success=True, message=f"Resource deleted: {filename}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid filename")
    except Exception as e:
        print(f"Error deleting resource: {e}")
        raise HTTPException(status_code=500, detail=str(e))
