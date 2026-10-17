import sqlite3
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import time
import re
import os
import httpx
import logging
import json
import hashlib
from pathlib import Path
from dotenv import load_dotenv
import uvicorn
from typing import Optional, List, Dict, Any
from sentence_transformers import SentenceTransformer, util
import torch # May be needed depending on sentence-transformers version/setup
import asyncio

load_dotenv()

import llm_client
import pedagogy
from config_loader import (
    get_config, section, agent_name, model_override, fill_placeholders,
    read_input, load_text_dir, INPUTS_DIR,
)
from learning_story import build_canvas, canvas_to_prompt, store_student_logs, pad_id_for
from learner_model import update_rule_based_state
from teacher_view import router as teacher_router

# --- Configuration ---
DATABASE_FILE = os.getenv("DATABASE_FILE", "/app/chat_histories/chat_history.db")
EXPERIMENT_CONFIG_FILE = INPUTS_DIR / "ab_experiments.json"
EA_URL = os.getenv("EA_URL", "http://localhost:8003/expert_query")

# --- Default Values (used if file loading fails) ---
DEFAULT_LEARNING_OBJECTIVES = [
    "Use Python", "Use proper syntax"
]
DEFAULT_ASSIGNMENT_DESCRIPTION = "Complete the assignment using Python. Focus on syntax and logic."
DEFAULT_TA_SYSTEM_PROMPT = "You are a helpful tutor named {agent_name}, embedded in a Jupyterlab Interface."
DEFAULT_NEXT_STEPS = ["Proceed to next assignment.", "Ask the tutor for exercises."]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TA - %(message)s', force=True)
logging.info(f"LLM settings: {llm_client.get_settings().describe()}")


# --- Load Content from Files ---
def load_assignment_resources():
    """Load assignment descriptions, learning objectives and next steps.

    The files are read on each call, so teachers can change them without a restart.
    Each '<assignment>.txt' file applies to the chat or notebook with the same name.
    """
    descs = load_text_dir("assignment_descriptions")
    los = load_text_dir("learning_objectives", as_lines=True)
    next_steps = load_text_dir("next_steps", as_lines=True)
    return descs, los, next_steps


def derive_assignment_id(file_name: str) -> str:
    # strip directory + extension
    return os.path.splitext(os.path.basename(file_name))[0]


def assignment_context(file_name: str):
    """Return (description, learning objectives, next steps) for a chat file."""
    descs, los, next_steps = load_assignment_resources()
    assignment_id = derive_assignment_id(file_name)
    return (
        descs.get(assignment_id) or descs.get("default") or DEFAULT_ASSIGNMENT_DESCRIPTION,
        los.get(assignment_id) or los.get("default") or DEFAULT_LEARNING_OBJECTIVES,
        next_steps.get(assignment_id) or next_steps.get("default") or DEFAULT_NEXT_STEPS,
    )


app = FastAPI(title="Multi-Agent Flow")
app.include_router(teacher_router)

# --- Global variable for experiment config ---
ACTIVE_EXPERIMENT_CONFIG = None
_EXPERIMENT_FILE_STAMP = None


def reload_experiment_config_if_changed():
    """Read ab_experiments.json again when the file changed on disk."""
    global _EXPERIMENT_FILE_STAMP
    try:
        stamp = EXPERIMENT_CONFIG_FILE.stat().st_mtime_ns
    except OSError:
        stamp = None
    if stamp != _EXPERIMENT_FILE_STAMP:
        _EXPERIMENT_FILE_STAMP = stamp
        load_experiment_config()

# --- Function to load experiment configuration ---
def load_experiment_config():
    global ACTIVE_EXPERIMENT_CONFIG
    try:
        with open(EXPERIMENT_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            active_id = config.get("active_experiment_id")
            if not active_id:
                logging.info("A/B testing: no active experiment.")
                ACTIVE_EXPERIMENT_CONFIG = None
            elif active_id in config.get("experiments", {}):
                ACTIVE_EXPERIMENT_CONFIG = config["experiments"][active_id]
                ACTIVE_EXPERIMENT_CONFIG["id"] = active_id # Store the active experiment ID itself
                logging.info(f"Successfully loaded active A/B experiment config: {active_id}")
            else:
                logging.warning(f"A/B testing: active_experiment_id '{active_id}' not found in {EXPERIMENT_CONFIG_FILE}. A/B testing disabled.")
                ACTIVE_EXPERIMENT_CONFIG = None
    except FileNotFoundError:
        logging.info(f"A/B testing: Experiment config file {EXPERIMENT_CONFIG_FILE} not found. A/B testing disabled.")
        ACTIVE_EXPERIMENT_CONFIG = None
    except json.JSONDecodeError:
        logging.error(f"A/B testing: Error decoding JSON from {EXPERIMENT_CONFIG_FILE}. A/B testing disabled.")
        ACTIVE_EXPERIMENT_CONFIG = None
    except Exception as e:
        logging.error(f"A/B testing: Unexpected error loading experiment config: {e}. A/B testing disabled.")
        ACTIVE_EXPERIMENT_CONFIG = None


# --- Database Setup ---
def init_db():
    try:
        Path(DATABASE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            # Create chat history table (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    message_type TEXT NOT NULL, -- 'question' or 'response'
                    message_text TEXT NOT NULL,
                    message_classification TEXT, -- category from agent_config.yaml, or NULL for responses
                    file_name TEXT
                )
            """)
            # Create student profiles table (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    profile_data TEXT NOT NULL, -- Store profile as JSON string
                    PRIMARY KEY (student_id, file_name)
                )
            """)
            # Create student experiment assignments table (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_experiment_assignments (
                    student_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (student_id, experiment_id)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS learner_models (
                    student_id TEXT PRIMARY KEY,
                    profile_data TEXT NOT NULL,
                    last_updated REAL NOT NULL,
                    last_llm_eval REAL NOT NULL
                )
            """)
            conn.commit()
            logging.info("Database initialized (chat_history, student_profiles, student_experiment_assignments, & learner_models tables checked/created).")
    except sqlite3.Error as e:
        logging.error(f"Database initialization failed: {e}")
        raise

init_db()
reload_experiment_config_if_changed()

# --- Data Models ---
class StudentMessage(BaseModel):
    student_id: str
    message_text: str
    processed_logs: Optional[str] = None
    structured_logs: Optional[List[Dict[str, Any]]] = None
    file_name: str

# This model defines the response TA sends back to chat_interact
class TutorApiResponse(BaseModel):
    final_response: str

# --- Profile Helper Functions ---
DEFAULT_PROFILE = {
    "total_questions": 0,
    "category_counts": {},
    "last_examples": {},
    "category_streak": 0,
    "last_question_classification": None,
    "last_interaction_timestamp": 0.0,
    "needs_guidance_flag": False,
}


def get_student_profile(student_id: str, file_name: str) -> dict:
    """Retrieves student profile for a specific file from DB or returns default.

    Attempts to load the profile JSON string from the student_profiles table
    based on the composite key (student_id, file_name). If no profile exists
    or if the stored data is invalid JSON, it returns a default profile structure.
    """
    profile = json.loads(json.dumps(DEFAULT_PROFILE))
    profile["student_id"] = student_id
    profile["file_name"] = file_name
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT profile_data FROM student_profiles WHERE student_id = ? AND file_name = ?", (student_id, file_name))
            result = cursor.fetchone()
            if result:
                try:
                    profile.update(json.loads(result[0]))
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode profile JSON for {student_id} (file: {file_name}). Using default.")
    except sqlite3.Error as e:
        logging.error(f"DB error getting profile for {student_id} (file: {file_name}): {e}. Using default.")
    # Profiles of earlier versions have only the instrumental/executive fields.
    if not profile.get("category_counts"):
        legacy = {k: profile.get(f"{k}_count", 0) for k in ("instrumental", "executive", "other")}
        profile["category_counts"] = {k: v for k, v in legacy.items() if v}
    if not profile.get("category_streak") and profile.get("consecutive_executive_count"):
        profile["category_streak"] = profile["consecutive_executive_count"]
    return profile


def save_student_profile(student_id: str, file_name: str, category: str, streak: int, timestamp: float, question_text: str):
    """Updates the profile counts, streak, examples and flag for a specific file."""
    logging.info(f"Background task: Updating profile for {student_id} (file: {file_name}) with category: {category}")
    try:
        config = get_config()
        profile = get_student_profile(student_id, file_name)
        profile = pedagogy.update_profile(
            profile, category, streak, question_text, timestamp,
            config.get("classification") or {}, config.get("interventions") or {},
        )
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO student_profiles (student_id, file_name, profile_data)
                VALUES (?, ?, ?)
            """, (student_id, file_name, json.dumps(profile)))
            conn.commit()
        logging.info(f"Successfully updated profile for {student_id} (file: {file_name})")
    except Exception as e:
        logging.error(f"Error updating profile for {student_id} (file: {file_name}): {e}", exc_info=True)


def update_question_classification(student_id, file_name, message_text, classification):
    with sqlite3.connect(DATABASE_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE chat_history
            SET message_classification = ?
            WHERE id = (
                SELECT id FROM chat_history
                WHERE student_id = ? AND file_name = ? AND message_text = ? AND message_type = 'question'
                ORDER BY timestamp DESC
                LIMIT 1
            )
            """,
            (classification, student_id, file_name, message_text)
        )
        conn.commit()

# --- Helper Functions ---
def get_or_assign_experiment_group(student_id: str) -> Optional[dict]:
    reload_experiment_config_if_changed()
    if not ACTIVE_EXPERIMENT_CONFIG or not ACTIVE_EXPERIMENT_CONFIG.get("groups"):
        return None # A/B testing disabled or no groups defined

    experiment_id = ACTIVE_EXPERIMENT_CONFIG["id"]
    groups = ACTIVE_EXPERIMENT_CONFIG["groups"]
    num_groups = len(groups)

    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            # Check if student is already assigned
            cursor.execute("""
                SELECT group_id FROM student_experiment_assignments
                WHERE student_id = ? AND experiment_id = ?
            """, (student_id, experiment_id))
            row = cursor.fetchone()

            if row:
                assigned_group_id = row[0]
                for group in groups:
                    if group["group_id"] == assigned_group_id:
                        return group # Return the full group object
                logging.warning(f"Student {student_id} assigned to group '{assigned_group_id}' but group not found in current config for experiment '{experiment_id}'. Using default.")
                return groups[0]

            # Assign to a group using hashing
            hash_input = (student_id + experiment_id).encode('utf-8')
            hash_value = hashlib.sha256(hash_input).hexdigest()
            group_index = int(hash_value, 16) % num_groups
            assigned_group = groups[group_index]

            # Store the new assignment
            cursor.execute("""
                INSERT INTO student_experiment_assignments (student_id, experiment_id, group_id)
                VALUES (?, ?, ?)
            """, (student_id, experiment_id, assigned_group["group_id"]))
            conn.commit()
            logging.info(f"Assigned student {student_id} to group '{assigned_group['group_id']}' for experiment '{experiment_id}'.")
            return assigned_group

    except Exception as e:
        logging.error(f"Error during experiment group assignment for {student_id}: {e}")
        return groups[0] if groups else None


# --- Learning objective matching with sentence embeddings ---
embedding_model = None
_LO_EMBEDDING_CACHE: Dict[tuple, Any] = {}


def load_embedding_model():
    global embedding_model
    try:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        embedding_model = SentenceTransformer(os.getenv("EMBEDDING_MODEL", 'all-MiniLM-L6-v2'), device=device)
        logging.info(f"Sentence Transformer model loaded successfully on {device}.")
    except Exception as e:
        logging.error(f"Failed to load Sentence Transformer model: {e}")
        embedding_model = None


def select_learning_objective_embeddings(question_text: str, learning_objectives: list) -> str:
    """Selects the most relevant LO using sentence embeddings."""
    if not learning_objectives:
        return "No specific LO"
    if not embedding_model:
        logging.warning("Sentence Transformer model not available. Using the first LO.")
        return learning_objectives[0]

    try:
        key = tuple(learning_objectives)
        if key not in _LO_EMBEDDING_CACHE:
            _LO_EMBEDDING_CACHE[key] = embedding_model.encode(list(key), convert_to_tensor=True)
        lo_embeddings = _LO_EMBEDDING_CACHE[key]
        question_embedding = embedding_model.encode(question_text, convert_to_tensor=True)
        cosine_scores = util.cos_sim(question_embedding, lo_embeddings)[0]
        best_match_idx = torch.argmax(cosine_scores).item()
        best_score = cosine_scores[best_match_idx].item()

        threshold = float(section("identification").get("learning_objective_min_similarity", 0.4))
        selected_lo = learning_objectives[best_match_idx]
        if best_score >= threshold:
            logging.info(f"Matched LO (Embeddings) '{selected_lo}' with score {best_score:.4f}")
        else:
            logging.info(f"No strong embedding match found (best score: {best_score:.4f}). Using the best match.")
        return selected_lo
    except Exception as e:
        logging.error(f"Error during embedding similarity calculation: {e}")
        return "No specific LO"


def extract_session_id_from_filename(file_name: str, student_id: str) -> str:
    sanitized_file_name = re.sub(r'[^a-zA-Z0-9_]', '', file_name.replace(".chat", "").lower())
    sanitized_student_id = re.sub(r'[^a-zA-Z0-9_]', '', student_id.lower())
    return f"{sanitized_student_id}_{sanitized_file_name}"


async def call_llm(messages: list, role: str, purpose: str = "LLM call") -> str:
    """Calls the configured OpenAI-compatible LLM with the model of a role."""
    try:
        return await llm_client.call_llm(messages, role=role, model=model_override(role), purpose=purpose)
    except llm_client.LLMError as e:
        logging.error(str(e))
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))


# --- Database Functions ---
def add_to_history(student_id: str, message_type: str, message_text: str, message_classification: Optional[str] = None, file_name: Optional[str] = None):
    """Adds a message to the chat history in the database."""
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_history (student_id, timestamp, message_type, message_text, message_classification, file_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, time.time(), message_type, message_text, message_classification, file_name))
            conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Failed to add message to history: {e}")

def get_history(student_id: str, file_name: str, limit: int = 6) -> List[dict]:
    """Retrieves the last 'limit' messages for a specific student and file, ordered chronologically, formatted for LLM API."""
    history_for_llm = []
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT message_type, message_text
                FROM chat_history
                WHERE student_id = ? AND file_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (student_id, file_name, limit))
            history_rows = cursor.fetchall()
            history_rows.reverse() # Chronological order
            for row in history_rows:
                role = "user" if row["message_type"] == "question" else "assistant"
                history_for_llm.append({"role": role, "content": row["message_text"]})
    except sqlite3.Error as e:
        logging.error(f"Failed to retrieve/format history for {student_id} (file: {file_name}): {e}")
    return history_for_llm

def format_history_for_prompt(history_messages: list) -> str:
    """Formats a list of message dicts (from get_history, which are {'role': ..., 'content': ...}) into a simple string."""
    if not history_messages:
        return "No recent conversation history."
    name = agent_name()
    formatted_string = "Recent Conversation History:\n"
    for msg in history_messages:
        role = "Student" if msg.get("role") == "user" else name
        content = msg.get("content", "[message unavailable]")
        formatted_string += f"{role}: {content}\n"
    return formatted_string.strip()


def save_logs(student_id: str, structured_logs: Optional[List[Dict[str, Any]]]):
    if structured_logs:
        try:
            store_student_logs(student_id, structured_logs)
        except Exception as e:
            logging.error(f"Could not store activity logs for {student_id}: {e}")


# --- Chat commands ---
async def run_report_command(message: StudentMessage, report_cfg: dict) -> str:
    """Generates a performance report from the activity logs and the conversation history."""
    assignment_desc, learning_objs, next_steps = assignment_context(message.file_name)
    hist_str = format_history_for_prompt(get_history(message.student_id, message.file_name, limit=50))
    logs_ctx = message.processed_logs or "No activity logs."
    system_prompt = fill_placeholders(report_cfg.get("system_prompt", ""), {"agent_name": agent_name()})
    report_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"""
        [INTERNAL CONTEXT: DO NOT REVEAL SOURCES]
        Assignment:
        {assignment_desc}

        Learning Objectives:
        - {chr(10).join(learning_objs)}

        Full Activity Logs:
        {logs_ctx}

        Conversation History:
        {hist_str}

        Next Steps (suggest one for the student based on performance):
        {chr(10).join(next_steps)}
        [END INTERNAL CONTEXT]
        ---
        Please generate a reflective performance report of the student, for the student.
        """}
    ]
    return await call_llm(report_prompt, role="report", purpose="performance report generation")


def run_completion_command(message: StudentMessage, completion_cfg: dict) -> str:
    """Returns the completion code when the student has worked long enough."""
    min_minutes = float(completion_cfg.get("min_minutes", 15))
    min_questions = int(completion_cfg.get("min_questions", 1))
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MIN(timestamp) as first_interaction,
                       COUNT(CASE WHEN message_type = 'question' THEN 1 END) as question_count
                FROM chat_history
                WHERE student_id = ? AND file_name = ?
            """, (message.student_id, message.file_name))
            result = cursor.fetchone()
        first_interaction, question_count = result if result and result[0] else (time.time(), 0)
        session_minutes = (time.time() - first_interaction) / 60
        feedback_parts = []
        if session_minutes < min_minutes:
            feedback_parts.append(f"- Work for at least {min_minutes - session_minutes:.1f} more minutes (currently: {session_minutes:.1f} minutes)")
        if question_count < min_questions:
            feedback_parts.append(f"- Ask at least {min_questions - question_count} more questions (currently: {question_count} questions)")
        if feedback_parts:
            return f"""### Almost There!
To ensure a meaningful learning experience, please:

{chr(10).join(feedback_parts)}

You can try `{completion_cfg.get('trigger')}` again once you meet these requirements."""
    except sqlite3.Error as e:
        logging.error(f"Database error checking session requirements: {e}")
    return fill_placeholders(completion_cfg.get("message", "{code}"), {"code": completion_cfg.get("code", "")})


# --- API Endpoints ---
@app.post("/receive_student_message", response_model=TutorApiResponse)
async def receive_student_message(message: StudentMessage, background_tasks: BackgroundTasks):
    """
    Handles incoming student messages:
    1. Classifies the message with the categories of agent_config.yaml.
    2. Calls the EA with context (history, logs, LO, assignment, question), if enabled.
    3. Formulates the pedagogical response with the reactive intervention rules.
    4. Schedules a background task for the profile update.
    """
    config = get_config()
    classification_cfg = config.get("classification") or {}
    interventions_cfg = config.get("interventions") or {}
    commands_cfg = config.get("commands") or {}
    prompts_cfg = config.get("prompts") or {}
    name = agent_name()

    save_logs(message.student_id, message.structured_logs)

    # --- A/B Testing: Get student's group and parameters ---
    student_experiment_group = get_or_assign_experiment_group(message.student_id)
    current_ta_system_prompt_file = prompts_cfg.get("tutor_system_file", "ta_system_prompt.txt")
    reactive_hints_enabled = True
    if student_experiment_group and "params" in student_experiment_group:
        group_params = student_experiment_group["params"]
        current_ta_system_prompt_file = group_params.get("system_prompt_file", current_ta_system_prompt_file)
        # "none" switches the reactive hints off for this group.
        reactive_hints_enabled = group_params.get("profile_hint_strategy", "standard") != "none"
        logging.info(f"A/B Test: Student {message.student_id} in group '{student_experiment_group['group_id']}'.")

    # --- Chat commands ---
    command = message.message_text.strip().lower()
    report_cfg = commands_cfg.get("report") or {}
    completion_cfg = commands_cfg.get("completion") or {}
    if report_cfg.get("enabled", True) and command == str(report_cfg.get("trigger", "/report")).lower():
        return TutorApiResponse(final_response=await run_report_command(message, report_cfg))
    if completion_cfg.get("enabled") and command == str(completion_cfg.get("trigger", "/finish")).lower():
        return TutorApiResponse(final_response=run_completion_command(message, completion_cfg))

    start_time = time.time()
    current_timestamp = time.time()
    logging.info(f"TA received message from {message.student_id} (file: {message.file_name}): '{message.message_text[:100]}...'")

    # --- 0. Get Context ---
    student_profile = get_student_profile(message.student_id, message.file_name)
    conversation_history_messages = get_history(message.student_id, message.file_name, limit=6)
    formatted_history_for_ea = format_history_for_prompt(conversation_history_messages)

    logs_context = "No recent activity logs available."
    if message.processed_logs and message.processed_logs.strip():
        logs_context = message.processed_logs.strip()

    assignment_description, learning_objectives, _ = assignment_context(message.file_name)
    values = {"agent_name": name, "question": message.message_text}

    final_response = "I'm sorry, I encountered an issue processing your request. Please try again."
    classification_result = pedagogy.default_category(classification_cfg)

    try:
        # --- 1. Select Learning Objective ---
        learning_objective = select_learning_objective_embeddings(message.message_text, learning_objectives)

        # --- 2. Store Current Question ---
        add_to_history(
            student_id=message.student_id, message_type="question",
            message_text=message.message_text, message_classification=None,
            file_name=message.file_name
        )

        # --- 3. Parallel Classification of Question and EA Call ---
        async def classify_question():
            return await pedagogy.classify_message(
                message.message_text, classification_cfg,
                lambda msgs: call_llm(msgs, role="classification", purpose="question classification"),
                values,
            )

        async def call_expert_agent():
            if not section("expert_agent").get("enabled", True):
                return "No technical information for this question"
            try:
                session_id = extract_session_id_from_filename(message.file_name, message.student_id)
                ea_payload = {
                    "student_question": message.message_text,
                    "assignment_description": assignment_description,
                    "learning_objective": learning_objective,
                    "history": formatted_history_for_ea,
                    "logs": logs_context,
                    "session_id": session_id
                }
                async with httpx.AsyncClient() as client:
                    ea_api_response = await client.post(EA_URL, json=ea_payload, timeout=llm_client.get_settings().timeout)
                    ea_api_response.raise_for_status()
                    return ea_api_response.json()["response"]
            except Exception as e:
                logging.error(f"EA call failed: {e}. Using default EA response.")
                return "The expert agent could not provide an answer."

        classification_result, ea_response = await asyncio.gather(classify_question(), call_expert_agent())
        logging.info(f"Question classified as: {classification_result}")

        # --- 4. Select the reactive intervention ---
        previous_category = student_profile.get("last_question_classification")
        streak = pedagogy.next_streak(classification_result, previous_category, student_profile.get("category_streak", 0))
        hint_values = dict(values, **pedagogy.example_values(student_profile, pedagogy.category_names(classification_cfg)))
        hint = None
        if reactive_hints_enabled:
            hint = pedagogy.select_reactive_hint(interventions_cfg, classification_result, previous_category, streak, hint_values)
            if hint:
                logging.info(f"Intervention rule '{hint['name']}' applies for {message.student_id}")

        # --- 5. LLM Call: Formulate Pedagogical Response ---
        try:
            system_prompt_content = fill_placeholders(
                read_input(current_ta_system_prompt_file, DEFAULT_TA_SYSTEM_PROMPT), values)
            if hint:
                system_prompt_content += f"\n**Profile Hint ({hint['name']}):** {hint['hint']}"
            system_prompt_content += "\n"

            final_prompt_messages = [{"role": "system", "content": system_prompt_content}]
            final_prompt_messages.extend(conversation_history_messages)
            final_prompt_messages.append(
                {"role": "user", "content": f"""
                    [INTERNAL CONTEXT: DO NOT REVEAL SOURCES]
                    Assignment: {assignment_description}
                    Recent Activity Logs:
                    {logs_context}
                    Technical Information: "{ea_response}"
                    Question Classification: {classification_result}
                    [END INTERNAL CONTEXT]

                    ---
                    Student Question: "{message.message_text}"
                    ---

                    Based on the context above (including profile hints and history), formulate your response as {name}, focusing directly on answering or guiding the student regarding their specific question. Never reveal or mention internal information like learning objectives or the expert source."""
                }
            )
            final_response = await call_llm(final_prompt_messages, role="response", purpose="final pedagogical response formulation")
        except Exception as e:
            logging.error(f"LLM Call (Pedagogical Response) failed: {e}. Using default final response.")
            if isinstance(e, HTTPException) and e.status_code == 429:
                final_response = "I'm getting a lot of questions right now. Please wait a moment and ask again."

        # --- 6. Store Final Response ---
        add_to_history(
            student_id=message.student_id, message_type="response",
            message_text=final_response, message_classification=None,
            file_name=message.file_name
        )
        update_question_classification(message.student_id, message.file_name, message.message_text, classification_result)

        # --- 7. Schedule Background Task for Profile Update ---
        background_tasks.add_task(
            save_student_profile, message.student_id, message.file_name,
            classification_result, streak, current_timestamp, message.message_text,
        )

        logging.info(f"TA processing complete for {message.student_id} in {time.time() - start_time:.2f}s.")
        return TutorApiResponse(final_response=final_response)

    except Exception as e:
        logging.error(f"Unexpected error in TA handler for {message.student_id}: {e}", exc_info=True)
        return TutorApiResponse(final_response="I'm sorry, an error occurred while processing your request.")


@app.get("/verify_ta")
def verify():
    return {"message": "Tutor Agent (Sync Response) is working"}

@app.get("/health")
def health():
    return {"status": "ok", "llm": llm_client.get_settings().describe()}

@app.get("/agent_config")
def get_agent_config():
    """Returns the student-facing parts of the config, for the notebook clients."""
    config = get_config()
    return {
        "agent": config.get("agent", {}),
        "proactivity": {k: v for k, v in (config.get("proactivity") or {}).items() if k != "system_prompt"},
        "message_gateway": config.get("message_gateway", {}),
    }

class ProactivityRequest(BaseModel):
    student_id: str
    file_name: str
    processed_logs: str
    structured_logs: Optional[List[Dict[str, Any]]] = None

class ProactivityResponse(BaseModel):
    intervention: str
    reasoning: str = ""

@app.post("/evaluate_proactivity", response_model=ProactivityResponse)
async def evaluate_proactivity(request: ProactivityRequest):
    """
    Evaluates the student's recent logs and conversation history to determine
    if a proactive intervention is needed. Uses structured JSON output to
    separate internal reasoning from the student-facing message.
    """
    config = get_config()
    proactivity_cfg = config.get("proactivity") or {}
    save_logs(request.student_id, request.structured_logs)
    if not proactivity_cfg.get("enabled", True):
        return ProactivityResponse(intervention="NO_INTERVENTION", reasoning="Proactivity is disabled")

    logging.info(f"Evaluating proactivity for {request.student_id}...")
    name = agent_name()

    try:
        formatted_history = format_history_for_prompt(get_history(request.student_id, request.file_name, limit=10))
        assignment_desc, learning_objs, _ = assignment_context(request.file_name)

        # Build the Student Activity Canvas and update Learner Model
        try:
            canvas = build_canvas(request.student_id, pad_id=pad_id_for(request.student_id))
            canvas_text = canvas_to_prompt(canvas)
            learner_state = update_rule_based_state(request.student_id, canvas)
            learner_state_text = (
                f"\n=== LEARNER STATE ===\n"
                f"Knowledge Proficiency: {learner_state['knowledge']}\n"
                f"Metacognitive State: {learner_state['metacognition']['state']}\n"
                f"Affect/Emotion: {learner_state['affect']['state']}\n"
                f"=== END LEARNER STATE ===\n"
            )
        except Exception as ce:
            logging.warning(f"Failed to build canvas/model, falling back to raw logs: {ce}")
            canvas_text = f"Raw Activity Logs:\n{request.processed_logs}"
            learner_state_text = ""

        proactivity_prompt = [
            {"role": "system", "content": fill_placeholders(proactivity_cfg.get("system_prompt", ""), {"agent_name": name})},
            {"role": "user", "content": f"""Assignment: {assignment_desc}

Learning Objectives: {', '.join(learning_objs)}

{canvas_text}
{learner_state_text}
Recent Conversation History:
{formatted_history}

Respond with the JSON object only. No other text."""}
        ]

        intervention_response = await call_llm(proactivity_prompt, role="proactivity", purpose="proactivity evaluation")

        # Parse the structured JSON response
        reasoning = ""
        message = "NO_INTERVENTION"
        raw = intervention_response.strip()
        try:
            if "```" in raw:
                raw = re.sub(r'```(?:json)?\s*', '', raw).strip().rstrip('`').strip()
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            parsed = json.loads(match.group(0) if match else raw)
            reasoning = parsed.get("reasoning", "")
            message = parsed.get("message", "NO_INTERVENTION")
        except (json.JSONDecodeError, AttributeError):
            logging.warning(f"Failed to parse proactivity JSON, falling back to plain text: {raw[:100]}")
            message = raw

        if "NO_INTERVENTION" in message.upper():
            return ProactivityResponse(intervention="NO_INTERVENTION", reasoning=reasoning)

        # Server-side blocked pattern check (defense in depth — client also checks)
        gateway_config = config.get("message_gateway") or {}
        for pattern in gateway_config.get("blocked_patterns", []):
            if pattern.lower() in message.lower():
                logging.warning(f"Blocked pattern '{pattern}' found in proactive message for {request.student_id}. Suppressing.")
                return ProactivityResponse(intervention="NO_INTERVENTION", reasoning=f"Blocked: {pattern} found in message")

        if len(message.strip()) < gateway_config.get("min_message_length", 15):
            return ProactivityResponse(intervention="NO_INTERVENTION", reasoning="Message too short")

        logging.info(f"Proactive intervention generated for {request.student_id}: {message[:80]}...")
        add_to_history(
            student_id=request.student_id,
            message_type="response",
            message_text=message,
            message_classification=None,
            file_name=request.file_name
        )
        return ProactivityResponse(intervention=message, reasoning=reasoning)

    except Exception as e:
        logging.error(f"Error during proactivity evaluation: {e}", exc_info=True)
        return ProactivityResponse(intervention="NO_INTERVENTION", reasoning=str(e))


# Load the embedding model once at startup, outside the request handler.
load_embedding_model()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8004)
