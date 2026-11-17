# teacher_view.py
# FastAPI routes for the teacher dashboard, the learning story API and the
# teacher settings page. All routes need the teacher password (HTTP Basic
# authentication, user name TEACHER_USERNAME, password TEACHER_PASSWORD).

import json
import logging
import os
import secrets
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel

import course_materials
import llm_client
import teacher_assistant
from config_loader import INPUTS_DIR, config_error, model_override, section, validate_teacher_yaml
from learning_story import (
    get_all_students, build_learning_story, build_canvas, canvas_to_prompt, build_class_overview
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TEACHER_VIEW - %(message)s')

security = HTTPBasic(realm="JELAI teacher")


def require_teacher(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Check the teacher user name and password."""
    password = os.getenv("TEACHER_PASSWORD", "")
    username = os.getenv("TEACHER_USERNAME", "teacher")
    if not password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The teacher pages are disabled. Set TEACHER_PASSWORD in the .env file.",
        )
    user_ok = secrets.compare_digest(credentials.username.encode(), username.encode())
    password_ok = secrets.compare_digest(credentials.password.encode(), password.encode())
    if not (user_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect user name or password.",
            headers={"WWW-Authenticate": 'Basic realm="JELAI teacher"'},
        )
    return credentials.username


router = APIRouter(prefix="/teacher", tags=["teacher"], dependencies=[Depends(require_teacher)])

# Resolve paths
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

# Files that teachers can edit on the settings page.
EDITABLE_ROOT_SUFFIXES = (".yaml", ".json", ".txt")
EDITABLE_SUBDIRS = ("assignment_descriptions", "learning_objectives", "next_steps")


def _serve_template(name: str) -> HTMLResponse:
    template_path = os.path.join(TEMPLATE_DIR, name)
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(
            content=f"<h1>Template not found</h1><p>Missing templates/{name}</p>",
            status_code=500
        )


@router.get("/students")
def list_students():
    """List all active students with basic stats."""
    students = get_all_students()
    return {"students": students}


@router.get("/class")
def class_overview():
    """Return one row for each student, for the class overview."""
    interventions = section("interventions")
    return {"students": build_class_overview(needs_guidance_cfg=interventions.get("needs_guidance") or {})}


@router.get("/student/{student_id}/story")
def get_student_story(student_id: str, pad_id: Optional[str] = None):
    """Return the full learning story for a student."""
    story = build_learning_story(student_id, pad_id=pad_id)
    return story


@router.get("/student/{student_id}/canvas")
def get_student_canvas(student_id: str, pad_id: Optional[str] = None):
    """Return the raw activity canvas for a student."""
    canvas = build_canvas(student_id, pad_id=pad_id)
    return canvas


@router.get("/student/{student_id}/canvas-prompt")
def get_student_canvas_prompt(student_id: str, pad_id: Optional[str] = None):
    """Return the canvas formatted as LLM prompt text."""
    canvas = build_canvas(student_id, pad_id=pad_id)
    return {"prompt": canvas_to_prompt(canvas)}


@router.get("-view", response_class=HTMLResponse)
def teacher_dashboard():
    """Serve the teacher dashboard HTML page."""
    return _serve_template("teacher_dashboard.html")


@router.get("-settings", response_class=HTMLResponse)
def teacher_settings_page():
    """Serve the teacher settings HTML page."""
    return _serve_template("teacher_settings.html")


# ---------------------------------------------------------------------------
# Settings API
# ---------------------------------------------------------------------------

def _editable_path(relative: str) -> Path:
    """Return the absolute path of an editable input file, or raise 400."""
    relative = (relative or "").strip().lstrip("/")
    if relative.endswith(".sample"):
        relative = relative[: -len(".sample")]
    path = (INPUTS_DIR / relative).resolve()
    inputs = INPUTS_DIR.resolve()
    parent = path.parent
    allowed = (
        (parent == inputs and path.suffix in EDITABLE_ROOT_SUFFIXES)
        or (parent.parent == inputs and parent.name in EDITABLE_SUBDIRS and path.suffix == ".txt")
    )
    if not allowed or not path.name or path.name.startswith("."):
        raise HTTPException(status_code=400, detail=f"This file cannot be edited: {relative}")
    return path


def _file_entry(path: Path) -> dict:
    relative = str(path.relative_to(INPUTS_DIR.resolve()))
    sample = path.with_name(path.name + ".sample")
    return {"path": relative, "exists": path.is_file(), "has_sample": sample.is_file()}


@router.get("/settings/files")
def list_editable_files():
    """List the files that teachers can edit, grouped by section."""
    inputs = INPUTS_DIR.resolve()
    groups = {"configuration": [], "prompts": [], **{name: [] for name in EDITABLE_SUBDIRS}}
    seen = set()

    def add(group: str, path: Path):
        if path.name.endswith(".sample"):
            path = path.with_name(path.name[: -len(".sample")])
        if path in seen:
            return
        seen.add(path)
        groups[group].append(_file_entry(path))

    for path in sorted(inputs.iterdir()) if inputs.is_dir() else []:
        if not path.is_file():
            continue
        base = path.name[: -len(".sample")] if path.name.endswith(".sample") else path.name
        suffix = Path(base).suffix
        if suffix in (".yaml", ".json"):
            add("configuration", path)
        elif suffix == ".txt":
            add("prompts", path)
    for name in EDITABLE_SUBDIRS:
        directory = inputs / name
        for path in sorted(directory.iterdir()) if directory.is_dir() else []:
            if path.is_file() and (path.suffix == ".txt" or path.name.endswith(".txt.sample")):
                add(name, path)
    return {"groups": groups, "writable": os.access(inputs, os.W_OK)}


@router.get("/settings/file")
def read_editable_file(path: str):
    """Return the content of an input file. If it does not exist, return its sample."""
    target = _editable_path(path)
    source = target if target.is_file() else target.with_name(target.name + ".sample")
    if not source.is_file():
        return {"path": path, "content": "", "from_sample": False, "exists": False}
    return {
        "path": str(target.relative_to(INPUTS_DIR.resolve())),
        "content": source.read_text(encoding="utf-8"),
        "from_sample": source != target,
        "exists": target.is_file(),
    }


class FileUpdate(BaseModel):
    path: str
    content: str


def _validate_content(target: Path, content: str) -> dict:
    if target.suffix == ".yaml":
        if target.name == "agent_config.yaml":
            return validate_teacher_yaml(content)
        import yaml
        try:
            yaml.safe_load(content)
        except yaml.YAMLError as e:
            return {"errors": [f"YAML syntax error: {e}"], "warnings": []}
    elif target.suffix == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            return {"errors": [f"JSON syntax error: {e}"], "warnings": []}
    return {"errors": [], "warnings": []}


@router.post("/settings/validate")
def validate_file(update: FileUpdate):
    """Validate the content of a file without saving it."""
    return _validate_content(_editable_path(update.path), update.content)


def _save_file(target: Path, content: str) -> dict:
    """Validate and save an input file. Raise 422 if the content is not valid."""
    result = _validate_content(target, content)
    if result["errors"]:
        raise HTTPException(status_code=422, detail=result)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target.with_name(f".{target.name}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, target)
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail={"errors": [f"Could not save the file ({e}). Is the inputs directory read-only?"],
                    "warnings": []},
        )
    logging.info(f"Teacher saved {target}")
    return {"saved": str(target.relative_to(INPUTS_DIR.resolve())), **result}


@router.put("/settings/file")
def save_editable_file(update: FileUpdate):
    """Validate and save an input file. The tutor uses it for the next message."""
    return _save_file(_editable_path(update.path), update.content)


def _effective_settings() -> llm_client.LLMSettings:
    """Return the LLM settings with the models that the teacher set in agent_config.yaml."""
    base = llm_client.get_settings()
    models = {role: model_override(role) or name for role, name in base.models.items()}
    return llm_client.LLMSettings(base.provider, base.base_url, base.api_key, models,
                                  base.timeout, base.max_retries)


@router.get("/settings/status")
def settings_status():
    """Return the LLM settings (without the key) and the configuration error, if any."""
    return {
        "llm": _effective_settings().describe(),
        "providers": {name: preset["label"] for name, preset in llm_client.PROVIDER_PRESETS.items()},
        "config_error": config_error(),
    }


@router.post("/settings/llm-test")
async def test_llm():
    """Send a short request to each configured model and return the results."""
    return await llm_client.test_connection(_effective_settings())


# ---------------------------------------------------------------------------
# Course materials API
# ---------------------------------------------------------------------------

class StartNotebook(BaseModel):
    path: str = ""


def _materials_error(error: course_materials.MaterialsError) -> HTTPException:
    return HTTPException(status_code=400, detail={"errors": [str(error)]})


@router.get("/materials")
def get_materials():
    """List the course materials and the start notebook."""
    directory = course_materials.materials_dir()
    return {
        "files": course_materials.list_files(),
        "start_notebook": course_materials.get_start_notebook(),
        "writable": directory.is_dir() and os.access(directory, os.W_OK),
        "max_mb": course_materials.max_upload_bytes() // (1024 * 1024),
    }


@router.put("/materials/file")
async def upload_material(request: Request, path: str, extract: bool = False):
    """Save the body of the request as a file. A ZIP file is extracted if ``extract`` is true."""
    limit = course_materials.max_upload_bytes()
    if int(request.headers.get("content-length") or 0) > limit:
        raise HTTPException(status_code=413, detail={"errors": [f"The file is larger than {limit // (1024 * 1024)} MB."]})
    data = await request.body()
    try:
        if extract:
            saved = course_materials.extract_zip(data)
        else:
            saved = [course_materials.save_file(path, data)]
    except course_materials.MaterialsError as e:
        raise _materials_error(e)
    except OSError as e:
        raise HTTPException(status_code=500, detail={"errors": [f"The files cannot be saved: {e}"]})
    return {"saved": saved}


@router.delete("/materials/file")
def delete_material(path: str):
    """Delete a file or directory of the course materials."""
    try:
        course_materials.delete_path(path)
        if course_materials.get_start_notebook() and not (
            course_materials.materials_dir() / course_materials.get_start_notebook()
        ).is_file():
            course_materials.set_start_notebook("")
    except course_materials.MaterialsError as e:
        raise _materials_error(e)
    return {"deleted": path}


@router.put("/materials/start")
def set_start_notebook(body: StartNotebook):
    """Set the notebook that students see after login. An empty path removes it."""
    try:
        return {"start_notebook": course_materials.set_start_notebook(body.path)}
    except course_materials.MaterialsError as e:
        raise _materials_error(e)


# ---------------------------------------------------------------------------
# Help assistant API
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str
    content: str


class AssistantRequest(BaseModel):
    messages: List[ChatMessage]
    current_path: Optional[str] = None


class ApplyProposal(BaseModel):
    path: str
    content: str
    base_sha256: str


@router.get("/assistant.js")
def assistant_script():
    """Serve the script of the help panel. The teacher pages load it."""
    path = os.path.join(TEMPLATE_DIR, "assistant.js")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/javascript")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="templates/assistant.js is missing.")


@router.post("/assistant/chat")
async def assistant_chat(body: AssistantRequest):
    """Answer a question of the teacher. Return the text and the proposed file changes."""
    if not teacher_assistant.enabled():
        raise HTTPException(status_code=403, detail={"errors": [
            "The help assistant is off. Set teacher_assistant.enabled to true in agent_config.yaml."]})
    history = [m.model_dump() for m in body.messages]
    if not history or history[-1]["role"] != "user" or not history[-1]["content"].strip():
        raise HTTPException(status_code=400, detail={"errors": ["Write a question."]})
    current_path = None
    if body.current_path:
        try:
            current_path = str(_editable_path(body.current_path).relative_to(INPUTS_DIR.resolve()))
        except HTTPException:
            current_path = None
    settings = _effective_settings()
    state = teacher_assistant.server_state(settings.describe(), current_path)
    messages = teacher_assistant.build_messages(history, teacher_assistant.load_docs(), state)
    try:
        reply = await llm_client.call_llm(messages, role="assistant", purpose="teacher help assistant",
                                          settings=settings)
    except llm_client.LLMError as e:
        raise HTTPException(status_code=502, detail={"errors": [
            f"The LLM did not answer: {e}. Click 'Test connection' on the settings page."]})
    text, proposals = teacher_assistant.parse_reply(reply)
    prepared = [teacher_assistant.prepare_proposal(p, _editable_path, _validate_content) for p in proposals]
    return {"reply": text, "raw_reply": reply, "proposals": prepared}


@router.post("/assistant/apply")
def assistant_apply(body: ApplyProposal):
    """Save a proposed change. Refuse it if the file changed after the proposal."""
    target = _editable_path(body.path)
    relative = str(target.relative_to(INPUTS_DIR.resolve()))
    if teacher_assistant.disk_sha256(relative) != body.base_sha256:
        raise HTTPException(status_code=409, detail={"errors": [
            f"{relative} changed after the proposal. Ask the assistant again."], "warnings": []})
    return _save_file(target, body.content)
