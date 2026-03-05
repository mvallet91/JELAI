# learning_story.py
# Builds the Student Activity Canvas and Learning Story from unified sources.

import os
import json
import re
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from learner_model import get_learner_model
import httpx

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - LEARNING_STORY - %(message)s')

DATABASE_FILE = os.getenv("DATABASE_FILE", "/app/chat_histories/chat_history.db")
ETHERPAD_URL = os.getenv("ETHERPAD_URL", "http://etherpad-dev:9001")
ETHERPAD_API_KEY = os.getenv("ETHERPAD_API_KEY", "jelai_secret_api_key_123")
PROCESSED_LOGS_DIR = os.getenv("PROCESSED_LOGS_DIR", "/app/student-logs/processed")


# ---------------------------------------------------------------------------
# 1. Data collectors — pull raw data from each source
# ---------------------------------------------------------------------------

def get_processed_logs(logs_dir: str = PROCESSED_LOGS_DIR) -> List[Dict]:
    """Load ALL processed log JSON files and return a unified, sorted list."""
    all_logs = []
    if not os.path.isdir(logs_dir):
        logging.warning(f"Logs dir not found: {logs_dir}")
        return all_logs
    for fname in os.listdir(logs_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(logs_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                logs = json.load(f)
            if isinstance(logs, list):
                all_logs.extend(logs)
        except Exception as e:
            logging.error(f"Error reading {fpath}: {e}")
    all_logs.sort(key=lambda x: x.get("time", ""))
    return all_logs


def get_chat_history(student_id: Optional[str] = None, db_path: str = DATABASE_FILE) -> List[Dict]:
    """Pull chat history from the SQLite DB. Optionally filter by student_id."""
    rows = []
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            if student_id:
                c.execute(
                    "SELECT student_id, timestamp, message_type, message_text, message_classification, file_name "
                    "FROM chat_history WHERE student_id = ? ORDER BY timestamp", (student_id,))
            else:
                c.execute(
                    "SELECT student_id, timestamp, message_type, message_text, message_classification, file_name "
                    "FROM chat_history ORDER BY timestamp")
            for r in c.fetchall():
                rows.append(dict(r))
    except Exception as e:
        logging.error(f"Error reading chat history: {e}")
    return rows


def get_etherpad_text(pad_id: str) -> Optional[str]:
    """Fetch current pad text from the Etherpad HTTP API (sync)."""
    url = f"{ETHERPAD_URL}/api/1/getText"
    try:
        resp = httpx.get(url, params={"apikey": ETHERPAD_API_KEY, "padID": pad_id}, timeout=5.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("text", "")
    except Exception as e:
        logging.warning(f"Could not fetch Etherpad text for {pad_id}: {e}")
    return None


def get_all_students(db_path: str = DATABASE_FILE) -> List[Dict]:
    """List unique students from the chat history DB."""
    students = []
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT student_id, MIN(timestamp) as first_seen, MAX(timestamp) as last_seen, "
                "COUNT(*) as message_count "
                "FROM chat_history GROUP BY student_id ORDER BY last_seen DESC")
            for r in c.fetchall():
                students.append(dict(r))
    except Exception as e:
        logging.error(f"Error listing students: {e}")
    return students


# ---------------------------------------------------------------------------
# 2. Student Activity Canvas — structured summary for the LLM
# ---------------------------------------------------------------------------

def build_canvas(student_id: str, pad_id: str = "test_pad",
                 logs_dir: str = PROCESSED_LOGS_DIR,
                 db_path: str = DATABASE_FILE) -> Dict[str, Any]:
    """
    Build the Student Activity Canvas: a structured summary of what the student
    has done across Jupyter, Etherpad, and Chat.
    """
    logs = get_processed_logs(logs_dir)
    chat = get_chat_history(student_id, db_path)
    pad_text = get_etherpad_text(pad_id)

    # --- Jupyter analysis ---
    jupyter_events = [l for l in logs if l.get("event") != "Edited Pad"]
    executions = [l for l in jupyter_events if l.get("event") in ("Executed cells", "Executed cells with error")]
    errors = [l for l in executions if l.get("event") == "Executed cells with error"]
    successes = [l for l in executions if l.get("event") == "Executed cells"]

    # Extract concepts used from successful code
    concepts = set()
    last_output = ""
    for ex in successes:
        code = ex.get("input", "")
        output = ex.get("output", "")
        if output:
            last_output = output[:300]
        # Simple pattern matching for common pandas/python concepts
        if "import pandas" in code or "import pd" in code:
            concepts.add("pandas import")
        if ".read_csv" in code:
            concepts.add("pd.read_csv")
        if ".head()" in code:
            concepts.add("df.head()")
        if ".describe()" in code:
            concepts.add("df.describe()")
        if ".groupby(" in code:
            concepts.add("df.groupby()")
        if ".plot" in code or "plt." in code:
            concepts.add("matplotlib/plotting")
        if ".mean()" in code:
            concepts.add("df.mean()")
        if ".value_counts()" in code:
            concepts.add("df.value_counts()")
        if "for " in code:
            concepts.add("loops")
        if "def " in code:
            concepts.add("functions")

    # --- Etherpad analysis ---
    pad_word_count = len(pad_text.split()) if pad_text else 0
    pad_events = [l for l in logs if l.get("event") == "Edited Pad"]
    last_pad_edit = pad_events[-1].get("time", "") if pad_events else "never"

    # Extract key claims from pad text (sentences)
    key_claims = []
    if pad_text:
        # Strip the Etherpad boilerplate
        clean_text = re.sub(
            r"Welcome to Etherpad!.*?settings\.json\s*", "", pad_text,
            flags=re.DOTALL
        ).strip()
        sentences = re.split(r'[.!?\n]+', clean_text)
        key_claims = [s.strip() for s in sentences if len(s.strip()) > 10][:5]

    # Does the writing reference specific data?
    mentions_data = False
    if pad_text:
        data_indicators = ["rows", "columns", "%", "average", "mean", "survived",
                           "dataset", "titanic", "result", "output", "found that"]
        mentions_data = any(ind in pad_text.lower() for ind in data_indicators)

    # --- Chat analysis ---
    questions = [c for c in chat if c.get("message_type") == "question"]
    responses = [c for c in chat if c.get("message_type") == "response"]
    last_question = questions[-1].get("message_text", "")[:100] if questions else ""
    last_response_time = responses[-1].get("timestamp", 0) if responses else 0
    last_question_time = questions[-1].get("timestamp", 0) if questions else 0
    unanswered = last_question_time > last_response_time if questions else False

    # --- Cross-tool gap analysis ---
    gaps = []
    if successes and not pad_events:
        gaps.append({
            "type": "code_without_writeup",
            "detail": "Student has executed code but hasn't written anything in Etherpad yet."
        })
    elif successes and pad_events and not mentions_data:
        gaps.append({
            "type": "vague_writing",
            "detail": "Student has code output but Etherpad text doesn't reference specific data results."
        })
    if key_claims and not successes:
        gaps.append({
            "type": "claims_without_evidence",
            "detail": f"Etherpad contains claims ({key_claims[0][:50]}...) but no code has been executed to verify."
        })
    if len(errors) >= 3 and not questions:
        gaps.append({
            "type": "stuck_without_asking",
            "detail": f"Student has {len(errors)} execution errors but hasn't asked for help in chat."
        })
    if successes and last_output and not any("describe" in s or "statistics" in s for s in key_claims):
        gaps.append({
            "type": "unexplored_output",
            "detail": "Code produced data output but student hasn't explored or written about the patterns."
        })

    return {
        "student_id": student_id,
        "jupyter": {
            "total_executions": len(executions),
            "successful_executions": len(successes),
            "errors": len(errors),
            "last_successful_output": last_output,
            "concepts_used": sorted(concepts),
        },
        "etherpad": {
            "word_count": pad_word_count,
            "last_edit": last_pad_edit,
            "key_claims": key_claims,
            "mentions_data": mentions_data,
        },
        "chat": {
            "questions_asked": len(questions),
            "responses_received": len(responses),
            "last_question": last_question,
            "unanswered": unanswered,
        },
        "cross_tool_gaps": gaps,
    }


def canvas_to_prompt(canvas: Dict[str, Any]) -> str:
    """Format the canvas as a concise text block for the proactivity LLM prompt."""
    jupyter = canvas["jupyter"]
    etherpad = canvas["etherpad"]
    chat = canvas["chat"]
    gaps = canvas["cross_tool_gaps"]

    lines = [
        "=== STUDENT ACTIVITY CANVAS ===",
        "",
        f"JUPYTER NOTEBOOK: {jupyter['total_executions']} executions "
        f"({jupyter['successful_executions']} success, {jupyter['errors']} errors)",
        f"  Concepts used: {', '.join(jupyter['concepts_used']) or 'none yet'}",
    ]
    if jupyter["last_successful_output"]:
        lines.append(f"  Last output: {jupyter['last_successful_output'][:200]}")

    lines += [
        "",
        f"ETHERPAD REPORT: {etherpad['word_count']} words, last edit: {etherpad['last_edit']}",
        f"  References specific data: {'yes' if etherpad['mentions_data'] else 'no'}",
    ]
    if etherpad["key_claims"]:
        lines.append(f"  Key claims: {'; '.join(etherpad['key_claims'][:3])}")

    lines += [
        "",
        f"CHAT: {chat['questions_asked']} questions asked, "
        f"{chat['responses_received']} responses received",
    ]
    if chat["last_question"]:
        lines.append(f"  Last question: {chat['last_question']}")
    if chat["unanswered"]:
        lines.append("  ⚠ Last question is unanswered")

    if gaps:
        lines += ["", "CROSS-TOOL GAPS:"]
        for g in gaps:
            lines.append(f"  • [{g['type']}] {g['detail']}")

    lines.append("=== END CANVAS ===")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. Learning Story — narrative timeline for the teacher
# ---------------------------------------------------------------------------

def build_timeline(student_id: str, pad_id: str = "test_pad",
                   logs_dir: str = PROCESSED_LOGS_DIR,
                   db_path: str = DATABASE_FILE) -> List[Dict]:
    """
    Build a unified timeline of all student activity across tools,
    sorted chronologically.
    """
    events = []

    # --- Jupyter + Etherpad events from processed logs ---
    logs = get_processed_logs(logs_dir)
    for log in logs:
        event_type = log.get("event", "")
        timestamp = log.get("time", "")
        source = log.get("source", "jupyter")
        notebook = os.path.basename(log.get("notebook", ""))

        if event_type == "Edited Pad":
            source = "etherpad"
            content = log.get("content", "")
            # Summarize: last 100 chars of pad text
            clean = re.sub(r"Welcome to Etherpad!.*?settings\.json\s*", "", content, flags=re.DOTALL).strip()
            summary = clean[-100:] if len(clean) > 100 else clean
            events.append({
                "time": timestamp, "source": "etherpad", "type": "writing",
                "summary": f"Edited report: \"{summary}\"",
                "detail": clean
            })
        elif event_type == "Executed cells":
            code = log.get("input", "")[:150]
            output = log.get("output", "")[:100]
            events.append({
                "time": timestamp, "source": "jupyter", "type": "code_success",
                "summary": f"`{code}` → {output or 'no output'}",
                "detail": log.get("input", "")
            })
        elif event_type == "Executed cells with error":
            code = log.get("content", "")[:100]
            error = log.get("error", "")[:100]
            events.append({
                "time": timestamp, "source": "jupyter", "type": "code_error",
                "summary": f"Error: {error}",
                "detail": f"Code: {code}\nError: {error}"
            })
        elif event_type == "Inserted code from assistant":
            events.append({
                "time": timestamp, "source": "jupyter", "type": "assistant_code",
                "summary": f"Inserted code from Juno into cell",
                "detail": log.get("content", "")[:200]
            })
        elif event_type in ("Edited cell", "Added new cell"):
            events.append({
                "time": timestamp, "source": "jupyter", "type": "edit",
                "summary": f"{event_type} (cell {log.get('cell_index', '?')})",
                "detail": log.get("content", "")[:200]
            })

    # --- Chat events from DB ---
    chat = get_chat_history(student_id, db_path)
    for msg in chat:
        ts = msg.get("timestamp", 0)
        time_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else ""
        if msg["message_type"] == "question":
            events.append({
                "time": time_str, "source": "chat", "type": "question",
                "summary": f"Asked: \"{msg['message_text'][:100]}\"",
                "detail": msg["message_text"]
            })
        else:
            preview = msg["message_text"][:120].replace("\n", " ")
            events.append({
                "time": time_str, "source": "chat", "type": "answer",
                "summary": f"Juno: \"{preview}{'...' if len(msg['message_text']) > 120 else ''}\"",
                "detail": msg["message_text"][:300]
            })

    # Sort everything by time
    events.sort(key=lambda x: x.get("time", ""))

    # Deduplicate consecutive identical Etherpad events (keep last per minute)
    deduped = []
    for evt in events:
        if deduped and evt["source"] == "etherpad" and deduped[-1]["source"] == "etherpad":
            # Replace the previous etherpad event if within same minute
            if evt["time"][:16] == deduped[-1]["time"][:16]:
                deduped[-1] = evt
                continue
        deduped.append(evt)

    return deduped


def build_learning_story(student_id: str, pad_id: str = "test_pad",
                         logs_dir: str = PROCESSED_LOGS_DIR,
                         db_path: str = DATABASE_FILE) -> Dict[str, Any]:
    """
    Build the complete Learning Story for a student — the teacher's view.
    """
    canvas = build_canvas(student_id, pad_id, logs_dir, db_path)
    timeline = build_timeline(student_id, pad_id, logs_dir, db_path)
    chat = get_chat_history(student_id, db_path)
    learner_state = get_learner_model(student_id, db_path)

    # Session duration
    times = [t["time"] for t in timeline if t["time"]]
    if len(times) >= 2:
        try:
            start = datetime.strptime(times[0], "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(times[-1], "%Y-%m-%d %H:%M:%S")
            duration_mins = int((end - start).total_seconds() / 60)
            duration_str = f"{duration_mins // 60}h {duration_mins % 60}m"
        except Exception:
            duration_str = "unknown"
    else:
        duration_str = "< 1 min"

    # Auto-generated summary
    jupyter = canvas["jupyter"]
    etherpad = canvas["etherpad"]
    chat_data = canvas["chat"]

    summary_parts = []
    if jupyter["total_executions"] > 0:
        summary_parts.append(
            f"Executed {jupyter['total_executions']} code cells "
            f"({jupyter['errors']} errors). "
            f"Concepts explored: {', '.join(jupyter['concepts_used']) or 'basic Python'}."
        )
    if etherpad["word_count"] > 0:
        summary_parts.append(
            f"Wrote {etherpad['word_count']} words in report. "
            f"{'References specific data.' if etherpad['mentions_data'] else 'Writing is still general/informal.'}"
        )
    if chat_data["questions_asked"] > 0:
        summary_parts.append(f"Asked {chat_data['questions_asked']} questions in chat.")

    if canvas["cross_tool_gaps"]:
        gap_types = [g["type"] for g in canvas["cross_tool_gaps"]]
        if "code_without_writeup" in gap_types:
            summary_parts.append("Has code results but hasn't documented findings yet.")
        if "stuck_without_asking" in gap_types:
            summary_parts.append("Experiencing errors but hasn't asked for help.")
        if "vague_writing" in gap_types:
            summary_parts.append("Writing doesn't reference specific data findings.")

    summary = " ".join(summary_parts) if summary_parts else "No significant activity recorded yet."

    # Build insights
    insights = {
        "concepts_explored": jupyter["concepts_used"],
        "struggles": [],
        "writing_quality": "No writing yet",
        "code_vs_writing_gap": "N/A",
        "help_seeking": "No questions asked",
        "engagement_level": "Low"
    }

    if jupyter["errors"] > 0:
        insights["struggles"].append(f"{jupyter['errors']} code execution errors")
    if etherpad["word_count"] > 0:
        if etherpad["mentions_data"]:
            insights["writing_quality"] = "References specific data — good depth"
        else:
            insights["writing_quality"] = "Informal/general — hasn't connected writing to data yet"

    if jupyter["total_executions"] > 0 and etherpad["word_count"] > 0:
        if etherpad["mentions_data"]:
            insights["code_vs_writing_gap"] = "Good alignment between code and writing"
        else:
            insights["code_vs_writing_gap"] = "Code output not yet referenced in writing"

    if chat_data["questions_asked"] > 0:
        insights["help_seeking"] = (
            f"Asked {chat_data['questions_asked']} questions, "
            f"{chat_data['responses_received']} answered"
        )

    # Engagement level
    total_actions = jupyter["total_executions"] + len([t for t in timeline if t["source"] == "etherpad"]) + chat_data["questions_asked"]
    if total_actions > 10:
        insights["engagement_level"] = "High"
    elif total_actions > 3:
        insights["engagement_level"] = "Moderate"
    else:
        insights["engagement_level"] = "Low"

    # Recommendations
    recommendations = []
    if jupyter["total_executions"] == 0:
        recommendations.append("Student hasn't executed any code yet. May need a prompt to get started.")
    if etherpad["word_count"] < 20:
        recommendations.append("Very little writing. Consider asking them to document their approach.")
    if jupyter["errors"] > 2 and chat_data["questions_asked"] == 0:
        recommendations.append("Multiple errors without asking for help — may be frustrated or disengaged.")
    if not etherpad["mentions_data"] and jupyter["successful_executions"] > 0:
        recommendations.append("Has data results but writing is vague — needs guidance on connecting findings to report.")
    if chat_data["questions_asked"] == 0 and jupyter["total_executions"] > 3:
        recommendations.append("Active in code but never asked for help — either self-sufficient or not aware of chat.")

    return {
        "student_id": student_id,
        "session_duration": duration_str,
        "summary": summary,
        "timeline": timeline,
        "canvas": canvas,
        "insights": insights,
        "recommendations": recommendations,
        "learner_model": learner_state,
    }
