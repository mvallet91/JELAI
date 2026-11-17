"""The help assistant of the teacher pages.

The assistant answers questions of teachers about the configuration of
JELAI, for example "How do I change the prompt of the tutor?" or "How do I
add an assignment?". It uses two sources of knowledge:

1. The documentation: the Markdown files in ``TEACHER_DOCS_DIR``
   (default ``/app/docs``). The files are short, so all of them go into the
   prompt. A search index is not necessary.
2. The live state of the server: the teacher configuration, the list of
   input files, the course materials, the start notebook and the LLM
   settings. The API key and the student data never go into the prompt.

The assistant does not save files. It can propose a change to an input
file. A proposal is a set of find-and-replace edits. This module applies
the edits to the current file, validates the result and returns a diff.
The teacher reviews the diff and clicks "Apply". The apply route of
``teacher_view`` saves the file only if the file did not change since the
proposal.

Format of a proposal in the reply of the LLM::

    ```jelai-edit path=learning_objectives/Task2.txt
    <<<<<<< FIND
    text that is in the file now (empty: replace the full file)
    =======
    the new text
    >>>>>>> REPLACE
    ```

One proposal can contain more than one FIND/REPLACE block.

Environment variables:

``TEACHER_DOCS_DIR``
    The directory of the documentation. Default: /app/docs.
"""

import difflib
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import course_materials
from config_loader import INPUTS_DIR, config_error, get_config, section

DOCS_MAX_CHARS = 60000
FILE_MAX_CHARS = 12000
HISTORY_MAX_MESSAGES = 12
MESSAGE_MAX_CHARS = 6000
ASSIGNMENT_DIRS = ("assignment_descriptions", "learning_objectives", "next_steps")

EDIT_START = re.compile(r"^```jelai-edit\s+path=(?P<path>\S+)\s*$")
FIND_MARK = "<<<<<<< FIND"
SPLIT_MARK = "======="
REPLACE_MARK = ">>>>>>> REPLACE"

SYSTEM_PROMPT = """You are the help assistant of JELAI, for teachers.
JELAI is a learning environment: students work in JupyterLab notebooks and
chat with an AI tutor. Teachers configure the tutor on the settings page
(/teacher-settings) and follow the class on the dashboard (/teacher-view).

Your task: answer questions of the teacher about how to configure and use
JELAI. Use only the documentation and the server state below. If they do
not give the answer, say that you do not know, and tell the teacher where
to look. Do not invent settings, keys, files or pages.

Rules:
- Write in the language of the teacher. Use short, clear sentences.
- Give steps in the order that the teacher does them. Refer to the
  settings page by the names that it shows (for example "Course
  materials", "Learning objectives", "Save").
- Use the server state to make the answer specific. For example, name the
  notebooks that do not have learning objectives.
- You cannot see student data. For questions about students, refer the
  teacher to the dashboard.
- You cannot change the .env file, the course materials or the start
  notebook. Explain the steps for these.
- The teacher can edit the input files on the settings page. When a change
  to an input file helps, propose it in this exact format (the teacher
  reviews it and clicks Apply; nothing changes before that):

```jelai-edit path=<path relative to the inputs directory>
<<<<<<< FIND
<exact text that is in the file now>
=======
<new text>
>>>>>>> REPLACE
```

  The FIND text must be an exact copy of lines in the current file, with
  enough lines to be unique. Keep it short. To make a new file, or to
  replace a full file, leave the FIND part empty. One proposal can have
  more than one FIND/REPLACE block. Propose only changes that the teacher
  asked for. Do not change other lines. Keep the comments in YAML files.
- Editable paths: agent_config.yaml, ab_experiments.json, other .yaml,
  .json and .txt files in the inputs directory, and
  assignment_descriptions/<notebook>.txt, learning_objectives/<notebook>.txt
  and next_steps/<notebook>.txt. The <notebook> name is the name of the
  notebook without ".ipynb".
"""


# ---------------------------------------------------------------------------
# Knowledge
# ---------------------------------------------------------------------------

def docs_dir() -> Path:
    return Path(os.getenv("TEACHER_DOCS_DIR") or "/app/docs")


def load_docs(max_chars: int = DOCS_MAX_CHARS) -> str:
    """Return the text of all Markdown files in the docs directory."""
    directory = docs_dir()
    if not directory.is_dir():
        return ""
    parts, total = [], 0
    for path in sorted(directory.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        part = f"### File docs/{path.name}\n\n{text}\n"
        if total + len(part) > max_chars:
            part = part[: max(0, max_chars - total)] + "\n[The rest of this file is not shown.]\n"
        parts.append(part)
        total += len(part)
        if total >= max_chars:
            break
    return "\n".join(parts)


def _truncate(text: str, limit: int = FILE_MAX_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[The rest of this file is not shown.]"


def read_input_file(relative: str) -> Tuple[str, bool, bool]:
    """Return (content, exists, from_sample) of an input file.

    If the file does not exist, the content is the content of its sample
    file, or an empty string.
    """
    path = INPUTS_DIR.resolve() / relative
    if path.is_file():
        return path.read_text(encoding="utf-8"), True, False
    sample = path.with_name(path.name + ".sample")
    if sample.is_file():
        return sample.read_text(encoding="utf-8"), False, True
    return "", False, False


def _input_files() -> List[str]:
    """Return the relative paths of the input files (sample files without '.sample')."""
    inputs = INPUTS_DIR.resolve()
    names = set()
    if not inputs.is_dir():
        return []
    for path in inputs.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        relative = str(path.relative_to(inputs))
        if relative.endswith(".sample"):
            relative = relative[: -len(".sample")] + " (sample only)"
            if (inputs / relative.replace(" (sample only)", "")).is_file():
                continue
        names.add(relative)
    return sorted(names)


def _stems(directory: str) -> List[str]:
    path = INPUTS_DIR.resolve() / directory
    if not path.is_dir():
        return []
    return sorted({p.stem for p in path.glob("*.txt")})


def assignment_gaps(notebooks: List[str]) -> List[str]:
    """Return one line for each notebook that has no file in an assignment directory."""
    lines = []
    present = {name: set(_stems(name)) for name in ASSIGNMENT_DIRS}
    for notebook in notebooks:
        stem = Path(notebook).stem
        missing = [name for name in ASSIGNMENT_DIRS if stem not in present[name] and "default" not in present[name]]
        if missing:
            lines.append(f"- {notebook}: no file in " + ", ".join(f"{m}/{stem}.txt" for m in missing))
    return lines


def server_state(llm_description: Optional[Dict] = None, current_path: Optional[str] = None) -> str:
    """Return a text summary of the configuration on the server, for the prompt."""
    lines = ["## Server state", ""]

    if llm_description:
        lines.append("LLM settings (from the .env file and llm.models in agent_config.yaml):")
        lines.append(f"- provider: {llm_description.get('provider_label') or llm_description.get('provider')}")
        lines.append(f"- API key set: {'yes' if llm_description.get('api_key_set') else 'no'}")
        for role, model in (llm_description.get("models") or {}).items():
            lines.append(f"- model for {role}: {model}")
        lines.append("")

    error = config_error()
    if error:
        lines.append(f"ERROR in agent_config.yaml, the tutor uses the defaults now: {error}")
        lines.append("")

    config = get_config()
    categories = [
        (c.get("name") if isinstance(c, dict) else str(c))
        for c in (section("classification").get("categories") or [])
    ]
    rules = [r.get("name") or r.get("category") for r in (section("interventions").get("reactive") or {}).get("rules") or []
             if isinstance(r, dict)]
    lines.append(f"Tutor name: {section('agent').get('name') or 'Juno'}")
    lines.append(f"Classification categories: {', '.join(c for c in categories if c) or 'none'}")
    lines.append(f"Reactive rules: {', '.join(r for r in rules if r) or 'none'}")
    lines.append(f"Expert agent enabled: {(config.get('expert_agent') or {}).get('enabled', True)}")
    lines.append(f"Proactive messages enabled: {section('proactivity').get('enabled', True)}")
    lines.append("")

    lines.append("Input files (in the inputs directory):")
    lines.extend(f"- {name}" for name in _input_files())
    lines.append("")

    try:
        materials = course_materials.list_files()
        start = course_materials.get_start_notebook()
    except Exception:  # The materials directory can be missing in development.
        materials, start = [], ""
    notebooks = [f["path"] for f in materials if f["path"].endswith(".ipynb")]
    lines.append("Course materials: " + (", ".join(f["path"] for f in materials) or "no files"))
    lines.append(f"Start notebook: {start or 'none (students see the JupyterLab launcher)'}")
    gaps = assignment_gaps(notebooks)
    if gaps:
        lines.append("Notebooks with missing assignment files:")
        lines.extend(gaps)
    lines.append("")

    files = ["agent_config.yaml", "ta_system_prompt.txt"]
    if current_path and current_path not in files:
        files.append(current_path)
    for relative in files:
        try:
            content, exists, from_sample = read_input_file(relative)
        except (OSError, ValueError):
            continue
        if not content and not exists:
            continue
        note = " (the sample file; the teacher has no own copy yet)" if from_sample else ""
        open_note = " The teacher has this file open in the editor now." if relative == current_path else ""
        lines.append(f"### Current content of {relative}{note}.{open_note}")
        lines.append("```")
        lines.append(_truncate(content))
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def build_messages(history: List[Dict[str, str]], docs: str, state: str) -> List[Dict[str, str]]:
    """Return the messages for the LLM: the system prompt and the recent chat."""
    system = SYSTEM_PROMPT
    system += "\n\n## Documentation\n\n" + (docs or "The documentation is not available on this server.")
    system += "\n\n" + state
    messages = [{"role": "system", "content": system}]
    for item in history[-HISTORY_MAX_MESSAGES:]:
        role = item.get("role")
        content = str(item.get("content") or "")[:MESSAGE_MAX_CHARS]
        if role in ("user", "assistant") and content.strip():
            messages.append({"role": role, "content": content})
    return messages


# ---------------------------------------------------------------------------
# Proposals
# ---------------------------------------------------------------------------

@dataclass
class Proposal:
    path: str
    edits: List[Tuple[str, str]] = field(default_factory=list)
    error: str = ""


def parse_reply(reply: str) -> Tuple[str, List[Proposal]]:
    """Split the reply of the LLM into the text and the proposals.

    In the text, each proposal is replaced by the marker "[Proposal N]".
    """
    lines = reply.splitlines()
    out, proposals = [], []
    i = 0
    while i < len(lines):
        match = EDIT_START.match(lines[i].strip())
        if not match:
            out.append(lines[i])
            i += 1
            continue
        proposal = Proposal(path=match.group("path").strip().strip("'\"`"))
        i += 1
        state, find, replace = None, [], []
        closed = False
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            if stripped == FIND_MARK:
                state, find, replace = "find", [], []
            elif stripped == SPLIT_MARK and state == "find":
                state = "replace"
            elif stripped == REPLACE_MARK and state == "replace":
                proposal.edits.append(("\n".join(find), "\n".join(replace)))
                state = None
            elif stripped.startswith("```") and state is None:
                closed = True
                i += 1
                break
            elif state == "find":
                find.append(line)
            elif state == "replace":
                replace.append(line)
            i += 1
        if state is not None or (not closed and not proposal.edits):
            proposal.error = "The proposal is not complete."
        elif not proposal.edits:
            proposal.error = "The proposal has no change."
        proposals.append(proposal)
        out.append(f"[Proposal {len(proposals)}]")
    return "\n".join(out).strip(), proposals


def _find_span(content: str, find: str) -> Tuple[int, int]:
    """Return the (start, end) of ``find`` in ``content``.

    First try an exact match, then a match that ignores spaces at the end
    of the lines. Raise ValueError if the text is not found or if it is
    found more than one time.
    """
    count = content.count(find)
    if count == 1:
        start = content.index(find)
        return start, start + len(find)
    if count > 1:
        raise ValueError("The text to replace is in the file more than one time.")
    # Compare line by line, without the spaces at the end.
    content_lines = content.splitlines(keepends=True)
    find_lines = [line.rstrip() for line in find.strip("\n").splitlines()]
    if not find_lines:
        raise ValueError("The text to replace is empty.")
    matches = []
    for index in range(len(content_lines) - len(find_lines) + 1):
        window = [line.rstrip() for line in content_lines[index:index + len(find_lines)]]
        if window == find_lines:
            matches.append(index)
    if len(matches) != 1:
        raise ValueError("The text to replace is not in the file." if not matches
                         else "The text to replace is in the file more than one time.")
    start = sum(len(line) for line in content_lines[: matches[0]])
    end = start + sum(len(line) for line in content_lines[matches[0]: matches[0] + len(find_lines)])
    if content_lines[matches[0] + len(find_lines) - 1].endswith("\n"):
        end -= 1
    return start, end


def apply_edits(content: str, edits: List[Tuple[str, str]]) -> str:
    """Apply find-and-replace edits to a text. An empty find replaces the full text."""
    for find, replace in edits:
        if not find.strip():
            content = replace if replace.endswith("\n") or not replace else replace + "\n"
            continue
        start, end = _find_span(content, find)
        content = content[:start] + replace + content[end:]
    return content


def sha256(text: Optional[str]) -> str:
    """Return the hash of a file content. A missing file has the hash of ''."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def disk_sha256(relative: str) -> str:
    path = INPUTS_DIR.resolve() / relative
    return sha256(path.read_text(encoding="utf-8") if path.is_file() else "")


def prepare_proposal(
    proposal: Proposal,
    resolve_path: Callable[[str], Path],
    validate: Callable[[Path, str], Dict],
) -> Dict:
    """Apply a proposal to the current file and validate the result.

    ``resolve_path`` checks that the file is editable and returns its
    absolute path (it raises an exception if not). ``validate`` returns
    {"errors": [...], "warnings": [...]} for a path and a content.
    """
    result = {"path": proposal.path, "applicable": False, "error": proposal.error,
              "diff": "", "content": "", "base_sha256": "", "errors": [], "warnings": []}
    if proposal.error:
        return result
    try:
        target = resolve_path(proposal.path)
    except Exception as e:  # HTTPException or ValueError
        result["error"] = str(getattr(e, "detail", e))
        return result
    relative = str(target.relative_to(INPUTS_DIR.resolve()))
    result["path"] = relative
    current, exists, from_sample = read_input_file(relative)
    try:
        new_content = apply_edits(current, proposal.edits)
    except ValueError as e:
        result["error"] = f"{e} Ask again, or make the change in the editor."
        return result
    if new_content == current and exists:
        result["error"] = "The proposal does not change the file."
        return result
    label = relative + (" (sample)" if from_sample else "" if exists else " (new file)")
    result["diff"] = "".join(difflib.unified_diff(
        current.splitlines(keepends=True), new_content.splitlines(keepends=True),
        fromfile=label, tofile=relative, n=2,
    ))
    result["content"] = new_content
    result["base_sha256"] = disk_sha256(relative)
    result["new_file"] = not exists
    result.update(validate(target, new_content))
    result["applicable"] = not result["errors"]
    return result


def enabled() -> bool:
    value = section("teacher_assistant").get("enabled", True)
    return value is not False and str(value).lower() not in ("false", "no", "0")

