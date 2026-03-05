# teacher_view.py
# FastAPI routes for the teacher dashboard and learning story API.

import os
import logging
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from learning_story import (
    get_all_students, build_learning_story, build_canvas, canvas_to_prompt
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TEACHER_VIEW - %(message)s')

router = APIRouter(prefix="/teacher", tags=["teacher"])

# Resolve paths
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


@router.get("/students")
def list_students():
    """List all active students with basic stats."""
    students = get_all_students()
    return {"students": students}


@router.get("/student/{student_id}/story")
def get_student_story(student_id: str, pad_id: str = "test_pad"):
    """Return the full learning story for a student."""
    story = build_learning_story(student_id, pad_id=pad_id)
    return story


@router.get("/student/{student_id}/canvas")
def get_student_canvas(student_id: str, pad_id: str = "test_pad"):
    """Return the raw activity canvas for a student."""
    canvas = build_canvas(student_id, pad_id=pad_id)
    return canvas


@router.get("/student/{student_id}/canvas-prompt")
def get_student_canvas_prompt(student_id: str, pad_id: str = "test_pad"):
    """Return the canvas formatted as LLM prompt text."""
    canvas = build_canvas(student_id, pad_id=pad_id)
    return {"prompt": canvas_to_prompt(canvas)}


@router.get("-view", response_class=HTMLResponse)
def teacher_dashboard():
    """Serve the teacher dashboard HTML page."""
    template_path = os.path.join(TEMPLATE_DIR, "teacher_dashboard.html")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content="<h1>Template not found</h1><p>Missing templates/teacher_dashboard.html</p>",
            status_code=500
        )
