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
import logging

# Course management
# Legacy JSON file course helpers (will be supplanted by DB-backed logic but kept for backward compatibility of some tests)
from courses import list_courses as file_list_courses, get_course as file_get_course, create_course as file_create_course, assign_teacher as file_assign_teacher, enroll_student as file_enroll_student, unenroll_student as file_unenroll_student, load_courses as file_load_courses

# --- SQLAlchemy ORM imports ---
from app import database as orm_database
from app import models as orm_models
from sqlalchemy.orm import Session, sessionmaker, joinedload
from sqlalchemy import create_engine
import importlib
import importlib.util

# Session dependency
def get_db():
    db = orm_database.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Initialize FastAPI app
app = FastAPI(title="JELAI Admin API", version="1.0.0")

logger = logging.getLogger('middleware_admin')

# Ensure DB schema exists and run idempotent initialization/seeding when available.
# Tests expect seeded users/courses; attempt to create tables and call the
# initialization script if present. Honor JELAI_SKIP_DB_INIT to skip in rare cases.
if os.environ.get('JELAI_SKIP_DB_INIT', '').lower() not in ('1', 'true', 'yes'):
    # If test harness sets COURSES_DATA_DIR, prefer a local sqlite DB there so
    # tests can run in isolated, writable dirs.
    try:
        courses_dir = os.environ.get('COURSES_DATA_DIR')
        if courses_dir:
            dbfile = os.path.join(courses_dir, 'jelai_test.db')
            dburl = f"sqlite:///{dbfile}"
            try:
                orm_database.engine = create_engine(dburl, connect_args={"check_same_thread": False})
                # Recreate SessionLocal bound to the overridden engine
                orm_database.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=orm_database.engine)
            except Exception:
                logger.exception('Failed to override orm database engine for tests')
    except Exception:
        logger.exception('Error preparing test DB override')
    try:
        orm_models.Base.metadata.create_all(bind=orm_database.engine)
    except Exception:
        logger.exception('Failed to create DB schema (continuing)')
    try:
        # Try to run scripts/initialize_db.py if present (idempotent)
        init_mod = None
        try:
            init_mod = importlib.import_module('scripts.initialize_db')
        except Exception:
            # try relative path import fallback
            init_path = os.path.join(os.path.dirname(__file__), 'scripts', 'initialize_db.py')
            if os.path.exists(init_path):
                spec = importlib.util.spec_from_file_location('scripts.initialize_db', init_path)
                init_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(init_mod)
        if init_mod and hasattr(init_mod, 'init_db'):
            try:
                init_mod.init_db()
            except Exception:
                logger.exception('scripts.initialize_db.init_db() failed (continuing)')
    except Exception:
        logger.exception('DB initialization import failed (continuing)')

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

# Base paths — use an environment-overridable application root so tests can run
# In container runtime the CWD will normally be '/app', while in local tests
# we prefer the repository working directory. Use JELAI_APP_ROOT to override.
APP_ROOT = os.environ.get('JELAI_APP_ROOT') or os.getcwd()

INPUTS_DIR = os.path.join(APP_ROOT, 'inputs')
MATERIALS_DIR = os.path.join(APP_ROOT, 'learning_materials')
WORKSPACE_TEMPLATES_DIR = os.path.join(APP_ROOT, 'workspace_templates')
SHARED_RESOURCES_DIR = os.path.join(APP_ROOT, 'shared_resources')
CHAT_DB_PATH = os.path.join(APP_ROOT, 'chat_histories', 'chat_history.db')
BUILD_STATUS_FILE = os.path.join(APP_ROOT, 'logs', 'build_status.txt')

# Ensure directories exist (safe in tests where APP_ROOT is writable)
try:
    os.makedirs(INPUTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(INPUTS_DIR, 'learning_objectives'), exist_ok=True)
    os.makedirs(MATERIALS_DIR, exist_ok=True)
    os.makedirs(WORKSPACE_TEMPLATES_DIR, exist_ok=True)
    os.makedirs(SHARED_RESOURCES_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CHAT_DB_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(BUILD_STATUS_FILE), exist_ok=True)
except PermissionError:
    # Fall back to a per-user temporary directory if APP_ROOT isn't writable.
    # This prevents test import-time failures when '/app' is not writable.
    import tempfile
    TMP_ROOT = tempfile.mkdtemp(prefix='jelai_local_')
    INPUTS_DIR = os.path.join(TMP_ROOT, 'inputs')
    MATERIALS_DIR = os.path.join(TMP_ROOT, 'learning_materials')
    WORKSPACE_TEMPLATES_DIR = os.path.join(TMP_ROOT, 'workspace_templates')
    SHARED_RESOURCES_DIR = os.path.join(TMP_ROOT, 'shared_resources')
    CHAT_DB_PATH = os.path.join(TMP_ROOT, 'chat_histories', 'chat_history.db')
    BUILD_STATUS_FILE = os.path.join(TMP_ROOT, 'logs', 'build_status.txt')
    os.makedirs(INPUTS_DIR, exist_ok=True)
    os.makedirs(os.path.join(INPUTS_DIR, 'learning_objectives'), exist_ok=True)
    os.makedirs(MATERIALS_DIR, exist_ok=True)
    os.makedirs(WORKSPACE_TEMPLATES_DIR, exist_ok=True)
    os.makedirs(SHARED_RESOURCES_DIR, exist_ok=True)
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


class CourseCreateRequest(BaseModel):
    title: str
    description: Optional[str] = ""


class CourseResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    materials: List[str]
    teachers: List[str]
    students: List[str]

class InternalUserInfo(BaseModel):
    username: str
    role: Optional[str]
    teaching: List[int]
    enrolled: List[int]

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


# --- Backwards-compatible wrappers for legacy file-based course helpers ---
def get_course(course_id: str):
    """Compatibility wrapper so tests and other code can patch admin_api.get_course
    Delegates to the legacy file_get_course implementation by default.
    """
    return file_get_course(course_id)


def list_courses():
    """Compatibility wrapper returning list of courses (legacy file-based or DB callers may use).
    """
    return file_list_courses()


def create_course(title: str, description: str = ""):
    """Compatibility wrapper for legacy create_course helper.
    """
    # Prefer DB-backed creation when possible, but fall back to legacy file storage.
    try:
        # Use SQLAlchemy session if available
        db = orm_database.SessionLocal()
        try:
            course = orm_models.Course(name=title, description=description, learning_materials_path=title.lower().replace(' ', '-'))
            db.add(course)
            db.commit()
            db.refresh(course)
            return {
                'id': str(course.id),
                'title': course.name,
                'description': course.description,
                'materials': [],
                'teachers': [],
                'students': []
            }
        finally:
            db.close()
    except Exception:
        # Fallback to file-based helper
        return file_create_course(title, description)


def assign_teacher(course_id: str, teacher: str):
    """Compatibility wrapper for legacy assign_teacher helper.
    """
    # Try DB path first
    try:
        # allow course_id to be either int id or legacy uuid-like
        try:
            cid = int(course_id)
        except Exception:
            cid = None
        if cid:
            db = orm_database.SessionLocal()
            try:
                course = db.query(orm_models.Course).filter_by(id=cid).first()
                teacher_user = db.query(orm_models.User).filter_by(username=teacher).first()
                if not course:
                    raise KeyError('course not found')
                if teacher_user:
                    exists = any(t.username == teacher for t in course.teachers)
                    if not exists:
                        db.add(orm_models.CourseTeacher(course_id=course.id, teacher_id=teacher_user.id))
                        db.commit()
                return {
                    'id': str(course.id),
                    'title': course.name,
                    'description': course.description,
                    'materials': [],
                    'teachers': [t.username for t in course.teachers],
                    'students': [s.username for s in course.students]
                }
            finally:
                db.close()
    except KeyError:
        raise
    except Exception:
        # Fallback to legacy file helper
        try:
            return file_assign_teacher(course_id, teacher)
        except KeyError:
            raise


def enroll_student(course_id: str, student: str):
    """Compatibility wrapper for legacy enroll_student helper.
    """
    try:
        try:
            cid = int(course_id)
        except Exception:
            cid = None
        if cid:
            db = orm_database.SessionLocal()
            try:
                course = db.query(orm_models.Course).filter_by(id=cid).first()
                if not course:
                    raise KeyError('course not found')
                stud_user = db.query(orm_models.User).filter_by(username=student).first()
                if not stud_user:
                    raise KeyError('student not found')
                exists = any(s.username == student for s in course.students)
                if not exists:
                    db.add(orm_models.Enrollment(course_id=course.id, student_id=stud_user.id))
                    db.commit()
                return {
                    'id': str(course.id),
                    'title': course.name,
                    'description': course.description,
                    'materials': [],
                    'teachers': [t.username for t in course.teachers],
                    'students': [s.username for s in course.students]
                }
            finally:
                db.close()
    except KeyError:
        raise
    except Exception:
        return file_enroll_student(course_id, student)


def unenroll_student(course_id: str, student: str):
    """Compatibility wrapper for legacy unenroll_student helper.
    """
    try:
        try:
            cid = int(course_id)
        except Exception:
            cid = None
        if cid:
            db = orm_database.SessionLocal()
            try:
                course = db.query(orm_models.Course).filter_by(id=cid).first()
                if not course:
                    raise KeyError('course not found')
                stud_user = db.query(orm_models.User).filter_by(username=student).first()
                if stud_user:
                    exists = any(s.username == student for s in course.students)
                    if exists:
                        # find enrollment and delete
                        enrollment = db.query(orm_models.Enrollment).filter_by(course_id=course.id, student_id=stud_user.id).first()
                        if enrollment:
                            db.delete(enrollment)
                            db.commit()
                return {
                    'id': str(course.id),
                    'title': course.name,
                    'description': course.description,
                    'materials': [],
                    'teachers': [t.username for t in course.teachers],
                    'students': [s.username for s in course.students]
                }
            finally:
                db.close()
    except KeyError:
        raise
    except Exception:
        return file_unenroll_student(course_id, student)


# --- Simple RBAC helpers (stubbed for now) ---
def get_user_from_request(request: Request) -> str:
    print('DEBUG: get_user_from_request called, checking for X-Test-User header')
    """Extract a username from Authorization header, X-Test-User, or query for demo/testing."""
    # For test/dev: allow X-Test-User header to override user (used by test suite)
    x_test_user = request.headers.get('X-Test-User')
    if x_test_user:
        return x_test_user
    # If the proxy includes an X-JELAI-ADMIN header set to 'true', map that to the
    # configured admin username so middleware RBAC treats the request as admin.
    xadmin = request.headers.get('X-JELAI-ADMIN', '').lower()
    # Print headers for debugging (visible in container logs)
    try:
        print('DEBUG_HEADERS:', dict(request.headers))
    except Exception:
        pass
    if xadmin == 'true':
        logger.info(f"Detected X-JELAI-ADMIN header -> treating as admin ({os.environ.get('ADMIN_USER','admin')})")
        return os.environ.get('ADMIN_USER', 'admin')

    auth = request.headers.get('Authorization') or request.query_params.get('user')
    logger.info(f"Authorization header: {request.headers.get('Authorization')}, query user: {request.query_params.get('user')}")
    if not auth:
        return 'anonymous'
    # If header is like 'Bearer username' or just 'username'
    parts = auth.split()
    # If this looks like an OAuth token ("Bearer <token>" or "token <token>"),
    # try to introspect it against the Hub API to obtain the canonical username.
    if len(parts) == 2 and parts[0].lower() in ("bearer", "token"):
        token = parts[1]
        # If the token is a short username-like string, just return it. Otherwise
        # attempt Hub introspection. We use a heuristic: tokens are longer than
        # 20 characters in our environment.
        if len(token) <= 20 and token.isalnum():
            return token
        # Attempt to call Hub to resolve token->user. Use env var if available.
        HUB_API = os.environ.get('JUPYTERHUB_API_URL', 'http://jupyterhub:8080')
        try:
            import requests
            r = requests.get(f"{HUB_API}/hub/api/user", headers={"Authorization": f"token {token}"}, timeout=5)
            if r.status_code == 200:
                info = r.json()
                return info.get('name')
        except Exception as e:
            logger.debug(f"Hub introspection failed: {e}")
        # Fallback: return the token string (old behavior)
        return token
    # Otherwise, treat the last token as the username
    return parts[-1]


def is_teacher_of(course: dict, username: str) -> bool:
    return username in course.get('teachers', [])


def is_admin_user(username: str) -> bool:
    # For now, treat 'admin' or env ADMIN_USER as admin
    admin_user = os.environ.get('ADMIN_USER', 'admin')
    return username == admin_user

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


@app.get('/api/users/{username}')
async def get_user_details(username: str, db: Session = Depends(get_db)):
    """Gets detailed user info, including enrollments."""
    user = db.query(orm_models.User).options(
        joinedload(orm_models.User.enrollments).joinedload(orm_models.Enrollment.course)
    ).filter(orm_models.User.username == username).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    enrolled_courses = [{
        "id": enrollment.course.id,
        "name": enrollment.course.name,
        "description": enrollment.course.description
    } for enrollment in user.enrollments]

    return {
        "id": user.id,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.effective_role,
        "enrolled_courses": enrolled_courses
    }


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
async def get_student_analytics(course_id: Optional[str] = None, db: Session = Depends(get_db)):
    """Get student activity analytics. If course_id provided, scope to enrolled students of that course."""
    try:
        enrolled_students: List[str] = []
        if course_id:
            try:
                cid = int(course_id)
            except ValueError:
                raise HTTPException(status_code=400, detail='invalid course_id')
            course = db.query(orm_models.Course).filter_by(id=cid).first()
            if not course:
                raise HTTPException(status_code=404, detail='course not found')
            enrolled_students = [s.username for s in course.students]
            if not enrolled_students:
                return []
        if not os.path.exists(CHAT_DB_PATH):
            return []
        conn = sqlite3.connect(CHAT_DB_PATH)
        if enrolled_students:
            placeholders = ','.join('?' for _ in enrolled_students)
            query = f"""
                SELECT student_id as username, COUNT(*) as message_count, MIN(timestamp) as first_interaction, MAX(timestamp) as last_interaction
                FROM chat_history
                WHERE student_id IN ({placeholders})
                GROUP BY student_id ORDER BY message_count DESC
            """
            cursor = conn.execute(query, enrolled_students)
        else:
            query = """
                SELECT student_id as username, COUNT(*) as message_count, MIN(timestamp) as first_interaction, MAX(timestamp) as last_interaction
                FROM chat_history GROUP BY student_id ORDER BY message_count DESC
            """
            cursor = conn.execute(query)
        results = []
        for row in cursor:
            results.append({
                'username': row[0],
                'message_count': row[1],
                'first_interaction': row[2],
                'last_interaction': row[3]
            })
        conn.close()
        return results
    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Error loading analytics')
        raise HTTPException(status_code=500, detail=f'Error loading analytics: {e}')

@app.get("/api/analytics/build-status")
async def get_build_status():
    """Get container build status"""
    try:
        with open(BUILD_STATUS_FILE, 'r') as f:
            return {"status": f.read().strip()}
    except FileNotFoundError:
        return {"status": "No build information available"}


<<<<<<< HEAD
=======
@app.get("/api/courses/{course_id}/analytics")
async def get_course_analytics(course_id: str, request: Request, db: Session = Depends(get_db)):
    """Get student activity analytics for a specific course (DB first, fallback legacy)."""
    user = get_user_from_request(request)
    enrolled_students: List[str] = []
    try:
        cid = int(course_id)
    except ValueError:
        cid = None
    if cid is not None:
        course = db.query(orm_models.Course).filter_by(id=cid).first()
        if course:
            teachers = [t.username for t in course.teachers]
            if not (is_admin_user(user) or user in teachers):
                raise HTTPException(status_code=403, detail='Insufficient privileges')
            enrolled_students = [s.username for s in course.students]
    if not enrolled_students:  # fallback legacy JSON course file
        legacy = file_get_course(course_id)
        if not legacy:
            raise HTTPException(status_code=404, detail='Course not found')
        if not (is_admin_user(user) or is_teacher_of(legacy, user)):
            raise HTTPException(status_code=403, detail='Insufficient privileges')
        enrolled_students = legacy.get('students', [])
    if not enrolled_students:
        return []
    try:
        if not os.path.exists(CHAT_DB_PATH):
            return []
        conn = sqlite3.connect(CHAT_DB_PATH)
        placeholders = ','.join('?' for _ in enrolled_students)
        query = f"""
            SELECT student_id as username, COUNT(*) as message_count, MIN(timestamp) as first_interaction, MAX(timestamp) as last_interaction
            FROM chat_history WHERE student_id IN ({placeholders})
            GROUP BY student_id ORDER BY message_count DESC
        """
        cursor = conn.execute(query, enrolled_students)
        results = []
        for row in cursor:
            results.append({'username': row[0], 'message_count': row[1], 'first_interaction': row[2], 'last_interaction': row[3]})
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error loading course analytics for {course_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading analytics: {e}")

# --- Admin course management endpoints (DB only) ---
@app.get('/api/admin/courses')
async def admin_list_courses(req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail='admin privileges required')
    courses = db.query(orm_models.Course).all()
    return [{
        'id': c.id,
        'name': c.name,
        'description': c.description,
        'learning_materials_path': c.learning_materials_path,
        'teachers': [t.username for t in c.teachers],
        'students': [s.username for s in c.students]
    } for c in courses]

class AdminCourseCreate(BaseModel):
    name: str
    description: Optional[str] = ''
    learning_materials_path: str

@app.post('/api/admin/courses')
async def admin_create_course(payload: AdminCourseCreate, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail='admin privileges required')
    exists = db.query(orm_models.Course).filter_by(name=payload.name).first()
    if exists:
        raise HTTPException(status_code=409, detail='course name exists')
    course = orm_models.Course(name=payload.name, description=payload.description, learning_materials_path=payload.learning_materials_path)
    db.add(course)
    db.commit()
    db.refresh(course)
    return {'id': course.id, 'name': course.name}

@app.get('/api/admin/courses/{course_id}')
async def admin_get_course(course_id: int, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail='admin privileges required')
    course = db.query(orm_models.Course).filter_by(id=course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='course not found')
    return {
        'id': course.id,
        'name': course.name,
        'description': course.description,
        'learning_materials_path': course.learning_materials_path,
        'teachers': [t.username for t in course.teachers],
        'students': [s.username for s in course.students]
    }

class AssignTeachersPayload(BaseModel):
    usernames: List[str]

@app.post('/api/admin/courses/{course_id}/teachers')
async def admin_assign_teachers(course_id: int, payload: AssignTeachersPayload, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail='admin privileges required')
    course = db.query(orm_models.Course).filter_by(id=course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='course not found')
    for uname in payload.usernames:
        teacher_user = db.query(orm_models.User).filter_by(username=uname).first()
        if teacher_user:
            exists = any(t.username == uname for t in course.teachers)
            if not exists:
                db.add(orm_models.CourseTeacher(course_id=course.id, teacher_id=teacher_user.id))
    db.commit()
    return {'id': course.id, 'teachers': [t.username for t in course.teachers]}

class EnrollStudentsPayload(BaseModel):
    usernames: List[str]

@app.post('/api/courses/{course_id}/students')
async def teacher_enroll_students(course_id: int, payload: EnrollStudentsPayload, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    course = db.query(orm_models.Course).filter_by(id=course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='course not found')
    teachers = [t.username for t in course.teachers]
    if not (is_admin_user(user) or user in teachers):
        raise HTTPException(status_code=403, detail='insufficient privileges')
    for uname in payload.usernames:
        stu = db.query(orm_models.User).filter_by(username=uname).first()
        if stu and all(su.username != uname for su in course.students):
            db.add(orm_models.Enrollment(course_id=course.id, student_id=stu.id))
    db.commit()
    return {'id': course.id, 'students': [s.username for s in course.students]}

@app.get('/api/courses/{course_id}/students')
async def list_course_students(course_id: int, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    course = db.query(orm_models.Course).filter_by(id=course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='course not found')
    teachers = [t.username for t in course.teachers]
    if not (is_admin_user(user) or user in teachers):
        raise HTTPException(status_code=403, detail='insufficient privileges')
    return {'students': [s.username for s in course.students]}

@app.delete('/api/courses/{course_id}/students/{student_username}')
async def remove_course_student(course_id: int, student_username: str, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    course = db.query(orm_models.Course).filter_by(id=course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail='course not found')
    teachers = [t.username for t in course.teachers]
    if not (is_admin_user(user) or user in teachers):
        raise HTTPException(status_code=403, detail='insufficient privileges')
    link = db.query(orm_models.Enrollment).join(orm_models.User, orm_models.User.id == orm_models.Enrollment.student_id).filter(orm_models.Enrollment.course_id == course.id, orm_models.User.username == student_username).first()
    if link:
        db.delete(link)
        db.commit()
    return {'removed': student_username}


>>>>>>> f24a389 (WIP: multi-course design)
# --- Courses endpoints ---
@app.get('/api/courses')
async def api_list_courses(req: Request, db: Session = Depends(get_db)):
    """List courses visible to the caller using DB; fall back to file data if DB empty."""
    user = get_user_from_request(req)
    try:
        db_courses = db.query(orm_models.Course).all()
        def serialize(course: orm_models.Course):
            return {
                'id': str(course.id),
                'title': course.name,
                'description': course.description,
                'materials': [],
                'teachers': [t.username for t in course.teachers],
                'students': [s.username for s in course.students]
            }
        if db_courses:
            if is_admin_user(user):
                return [serialize(c) for c in db_courses]
            visible = []
            for c in db_courses:
                if user in [t.username for t in c.teachers] or user in [s.username for s in c.students]:
                    visible.append(serialize(c))
            return visible
        # Fallback legacy
        courses = file_list_courses()
        if is_admin_user(user):
            return courses
        return [c for c in courses if user in c.get('teachers', []) or user in c.get('students', [])]
    except Exception as e:
        logger.exception('Error listing courses')
        raise HTTPException(status_code=500, detail=str(e))


@app.post('/api/courses', response_model=CourseResponse)
async def api_create_course(request: CourseCreateRequest, req: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(req)
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail='admin privileges required')
    # Delegate creation to the compatibility wrapper so tests can patch it.
    created = create_course(title=request.title, description=request.description)
    return created


@app.get('/api/courses/{course_id}', response_model=CourseResponse)
<<<<<<< HEAD
async def api_get_course(course_id: str):
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail='course not found')
    return course
=======
async def api_get_course(course_id: str, request: Request, db: Session = Depends(get_db)):
    user = get_user_from_request(request)
    try:
        course = db.query(orm_models.Course).filter(orm_models.Course.id == int(course_id)).first()
    except ValueError:
        course = None
    if course:
        teachers = [t.username for t in course.teachers]
        students = [s.username for s in course.students]
        if not (is_admin_user(user) or user in teachers or user in students):
            raise HTTPException(status_code=403, detail='insufficient privileges')
        return {
            'id': str(course.id),
            'title': course.name,
            'description': course.description,
            'materials': [],
            'teachers': teachers,
            'students': students
        }
    # fallback legacy JSON
    legacy = file_get_course(course_id)
    if not legacy:
        raise HTTPException(status_code=404, detail='course not found')
    if not (is_admin_user(user) or is_teacher_of(legacy, user) or user in legacy.get('students', [])):
        raise HTTPException(status_code=403, detail='insufficient privileges')
    return legacy
>>>>>>> f24a389 (WIP: multi-course design)


@app.post('/api/courses/{course_id}/assign-teacher')
async def api_assign_teacher(course_id: str, teacher: str = Form(...), req: Request = None, db: Session = Depends(get_db)):
    user = get_user_from_request(req) if req else 'anonymous'
    if not is_admin_user(user):
        raise HTTPException(status_code=403, detail='admin privileges required')
    # DB first
    try:
        cid = int(course_id)
    except ValueError:
        cid = None
    if cid:
        course = db.query(orm_models.Course).filter_by(id=cid).first()
        teacher_user = db.query(orm_models.User).filter_by(username=teacher).first()
        if course and teacher_user:
            exists = any(t.username == teacher for t in course.teachers)
            if not exists:
                db.add(orm_models.CourseTeacher(course_id=course.id, teacher_id=teacher_user.id))
                db.commit()
            return {
                'id': str(course.id),
                'title': course.name,
                'description': course.description,
                'materials': [],
                'teachers': [t.username for t in course.teachers],
                'students': [s.username for s in course.students]
            }
    # Legacy fallback
    try:
        return file_assign_teacher(course_id, teacher)
    except KeyError:
        raise HTTPException(status_code=404, detail='course not found')


@app.post('/api/courses/{course_id}/enroll')
async def api_enroll_student(course_id: str, student: str = Form(...), req: Request = None, db: Session = Depends(get_db)):
    user = get_user_from_request(req) if req else 'anonymous'
    # DB path
    try:
        cid = int(course_id)
    except ValueError:
        cid = None
    if cid:
        course = db.query(orm_models.Course).filter_by(id=cid).first()
        if not course:
            raise HTTPException(status_code=404, detail='course not found')
        teachers = [t.username for t in course.teachers]
        if not (is_admin_user(user) or user in teachers):
            raise HTTPException(status_code=403, detail='insufficient privileges')
        stud_user = db.query(orm_models.User).filter_by(username=student).first()
        if not stud_user:
            raise HTTPException(status_code=404, detail='student user not found')
        exists = any(s.username == student for s in course.students)
        if not exists:
            db.add(orm_models.Enrollment(course_id=course.id, student_id=stud_user.id))
            db.commit()
        return {
            'id': str(course.id),
            'title': course.name,
            'description': course.description,
            'materials': [],
            'teachers': [t.username for t in course.teachers],
            'students': [s.username for s in course.students]
        }
    # legacy
    legacy = file_get_course(course_id)
    if not legacy:
        raise HTTPException(status_code=404, detail='course not found')
    if not (is_admin_user(user) or is_teacher_of(legacy, user)):
        raise HTTPException(status_code=403, detail='insufficient privileges')
    return file_enroll_student(course_id, student)


@app.post('/api/courses/{course_id}/unenroll')
async def api_unenroll_student(course_id: str, student: str = Form(...), req: Request = None, db: Session = Depends(get_db)):
    user = get_user_from_request(req) if req else 'anonymous'
    try:
        cid = int(course_id)
    except ValueError:
        cid = None
    if cid:
        course = db.query(orm_models.Course).filter_by(id=cid).first()
        if not course:
            raise HTTPException(status_code=404, detail='course not found')
        teachers = [t.username for t in course.teachers]
        if not (is_admin_user(user) or user in teachers):
            raise HTTPException(status_code=403, detail='insufficient privileges')
        # remove enrollment if exists
        link = db.query(orm_models.Enrollment).join(orm_models.User, orm_models.User.id == orm_models.Enrollment.student_id).filter(orm_models.Enrollment.course_id == course.id, orm_models.User.username == student).first()
        if link:
            db.delete(link)
            db.commit()
        return {
            'id': str(course.id),
            'title': course.name,
            'description': course.description,
            'materials': [],
            'teachers': [t.username for t in course.teachers],
            'students': [s.username for s in course.students]
        }
    legacy = file_get_course(course_id)
    if not legacy:
        raise HTTPException(status_code=404, detail='course not found')
    if not (is_admin_user(user) or is_teacher_of(legacy, user)):
        raise HTTPException(status_code=403, detail='insufficient privileges')
    return file_unenroll_student(course_id, student)

# --- Internal endpoints for JupyterHub integration ---
@app.get('/api/internal/user-info', response_model=InternalUserInfo)
async def internal_user_info(username: str, db: Session = Depends(get_db)):
    user = db.query(orm_models.User).filter_by(username=username).first()
    if not user:
        return InternalUserInfo(username=username, role=None, teaching=[], enrolled=[])
    role = user.effective_role
    teaching = [link.course_id for link in user.teaching_assignments]
    enrolled = [link.course_id for link in user.enrollments]
    return InternalUserInfo(username=username, role=role, teaching=teaching, enrolled=enrolled)


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
