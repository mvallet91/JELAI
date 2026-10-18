"""The course materials of the teacher.

The materials are files in one directory. This directory is a Docker volume.
The middleware writes to it, and the student notebooks and the hub read it.
Each student notebook copies the files to the work directory of the student.

The file ``course.yaml`` in the directory holds the course settings. At
this time, it has one key: ``start_notebook``, the notebook that opens after
login.

Environment variables:

``COURSE_MATERIALS_DIR``
    The directory of the materials. Default: /app/course_materials.
``COURSE_MATERIALS_MAX_MB``
    The maximum size of one upload, in megabytes. Default: 100.
"""

import io
import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

import yaml

COURSE_FILE = "course.yaml"
DEFAULT_MAX_MB = 100


class MaterialsError(ValueError):
    """The request cannot be done. The message is for the teacher."""


def materials_dir() -> Path:
    return Path(os.getenv("COURSE_MATERIALS_DIR") or "/app/course_materials")


def max_upload_bytes() -> int:
    try:
        megabytes = int(os.getenv("COURSE_MATERIALS_MAX_MB") or DEFAULT_MAX_MB)
    except ValueError:
        megabytes = DEFAULT_MAX_MB
    return megabytes * 1024 * 1024


def safe_path(relative: str, root: Optional[Path] = None) -> Path:
    """Return the absolute path of a file in the materials directory.

    Raises MaterialsError for an empty path, a path outside the directory,
    a hidden name, or the name of the course file.
    """
    root = (root or materials_dir()).resolve()
    relative = (relative or "").replace("\\", "/").strip().strip("/")
    parts = [p for p in relative.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise MaterialsError(f"This path is not valid: {relative!r}")
    if any(p.startswith(".") for p in parts):
        raise MaterialsError("Names that start with a dot are not allowed.")
    path = root.joinpath(*parts).resolve()
    if root not in path.parents:
        raise MaterialsError(f"This path is not valid: {relative!r}")
    if path.parent == root and path.name in (COURSE_FILE, "README.md"):
        raise MaterialsError(f"The name {path.name} is reserved.")
    return path


def _make_readable(path: Path) -> None:
    """The student notebooks run as another user and must read the files."""
    try:
        path.chmod(0o755 if path.is_dir() else 0o644)
    except OSError:
        pass


def _make_parents(path: Path, root: Path) -> None:
    current = path.parent
    missing = []
    while current != root and not current.exists():
        missing.append(current)
        current = current.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    for directory in missing:
        _make_readable(directory)


def list_files(root: Optional[Path] = None) -> List[Dict]:
    """List all files of the materials, sorted by path."""
    root = (root or materials_dir()).resolve()
    if not root.is_dir():
        return []
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in (COURSE_FILE, "README.md") or any(p.startswith(".") for p in relative.split("/")):
            continue
        entries.append({"path": relative, "size": path.stat().st_size})
    return entries


def save_file(relative: str, data: bytes, root: Optional[Path] = None) -> Dict:
    """Save one file. An existing file with the same path is replaced."""
    root = (root or materials_dir()).resolve()
    if len(data) > max_upload_bytes():
        raise MaterialsError(f"The file is larger than {max_upload_bytes() // (1024 * 1024)} MB.")
    path = safe_path(relative, root)
    if path.is_dir():
        raise MaterialsError(f"{relative} is a directory.")
    _make_parents(path, root)
    path.write_bytes(data)
    _make_readable(path)
    return {"path": path.relative_to(root).as_posix(), "size": len(data)}


def extract_zip(data: bytes, root: Optional[Path] = None) -> List[Dict]:
    """Extract a ZIP archive into the materials. Returns the saved files."""
    root = (root or materials_dir()).resolve()
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise MaterialsError("This is not a valid ZIP file.")
    limit = max_upload_bytes()
    members = [m for m in archive.infolist() if not m.is_dir()]
    if sum(m.file_size for m in members) > limit:
        raise MaterialsError(f"The files in the ZIP are larger than {limit // (1024 * 1024)} MB.")
    saved = []
    for member in members:
        name = member.filename.replace("\\", "/")
        parts = name.split("/")
        # Archives of macOS and Windows hold metadata files. Skip them.
        if parts[0] == "__MACOSX" or any(p.startswith(".") for p in parts) or parts[-1] == "Thumbs.db":
            continue
        saved.append(save_file(name, archive.read(member), root))
    if not saved:
        raise MaterialsError("The ZIP file has no files.")
    return saved


def delete_path(relative: str, root: Optional[Path] = None) -> None:
    """Delete a file, or a directory with its files."""
    root = (root or materials_dir()).resolve()
    path = safe_path(relative, root)
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
    else:
        raise MaterialsError(f"{relative} does not exist.")


def get_start_notebook(root: Optional[Path] = None) -> str:
    """Return the start notebook, or an empty string if there is none."""
    path = (root or materials_dir()) / COURSE_FILE
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return ""
    return str(data.get("start_notebook") or "").strip()


def set_start_notebook(relative: str, root: Optional[Path] = None) -> str:
    """Set the start notebook. An empty value removes the setting."""
    root = (root or materials_dir()).resolve()
    relative = (relative or "").strip()
    if relative:
        path = safe_path(relative, root)
        if path.suffix != ".ipynb" or not path.is_file():
            raise MaterialsError("The start notebook must be an .ipynb file in the course materials.")
        relative = path.relative_to(root).as_posix()
    root.mkdir(parents=True, exist_ok=True)
    course_file = root / COURSE_FILE
    course_file.write_text(yaml.safe_dump({"start_notebook": relative}), encoding="utf-8")
    _make_readable(course_file)
    return relative
