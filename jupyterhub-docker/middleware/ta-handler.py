import sqlite3
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
import time
import re
import os
import httpx
import logging
import json # Added
import hashlib # Added
from pathlib import Path # Added
from dotenv import load_dotenv
import uvicorn
from typing import Optional, List 
from thefuzz import process
from sentence_transformers import SentenceTransformer, util
import torch # May be needed depending on sentence-transformers version/setup
import glob
import asyncio

# --- Configuration ---
load_dotenv()

# DATABASE_FILE = "chat_history.db" # for local testing
DATABASE_FILE = "/app/chat_histories/chat_history.db"  # for docker
EXPERIMENT_CONFIG_FILE = Path(__file__).parent / "inputs" / "ab_experiments.json" # Added

EA_URL = "http://localhost:8003/expert_query" 

# Use .env variables or fall back to defaults
WEBUI_API_BASE = os.getenv("webui_url", "http://localhost:3000") 
WEBUI_API_KEY = os.getenv("webui_api_key", "")
OLLAMA_API_BASE = os.getenv("ollama_url", "http://localhost:11434") 

CLASSIFICATION_MODEL_NAME = os.getenv("ollama_classification_model", "gemma3:4b")
RESPONSE_MODEL_NAME = os.getenv("ollama_response_model", "gemma3:4b")

# General Inputs from Directories
ASSIGNMENT_DESC_DIR = "./inputs/assignment_descriptions"
LO_DIR = "./inputs/learning_objectives"
NEXT_STEPS_DIR = "./inputs/next_steps"

TA_SYSTEM_PROMPT_FILE = "./inputs/ta_system_prompt.txt"
CLASSIFICATION_PROMPT_FILE = "./inputs/classification_prompt.txt"
POSSIBLE_CLASSIFICATIONS_FILE = "./inputs/classification_options.txt"
TA_SYSTEM_PROMPT_FILE = "./inputs/ta_system_prompt.txt"

# --- Default Values (used if file loading fails) ---
DEFAULT_LEARNING_OBJECTIVES = [
    "Use Python", "Use proper syntax"
]
DEFAULT_ASSIGNMENT_DESCRIPTION = "Complete the assignment using Python. Focus on syntax and logic."
MIN_MATCH_SCORE = 70 # Minimum score (out of 100) to consider it a match
DEFAULT_TA_SYSTEM_PROMPT = "You are a helpful tutor named Juno, embedded in a Jupyterlab Interface." 
DEFAULT_CLASSIFICATION_PROMPT = "Classify the following question as good or bad"
DEFAULT_POSSIBLE_CLASSIFICATIONS = ["good", "bad"]

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TA - %(message)s')
logging.info(f"Using WebUI Base URL: {WEBUI_API_BASE}")
logging.info(f"Using Classification Model: {CLASSIFICATION_MODEL_NAME}")
logging.info(f"Using Response Model: {RESPONSE_MODEL_NAME}")

# --- Load Content from Files ---
def load_assignment_resources():
    descs = {}
    los = {}
    next = {}
    # Load assignment descriptions, learning objectives, and next steps from files
    if not os.path.exists(ASSIGNMENT_DESC_DIR):
        logging.error(f"Assignment descriptions directory '{ASSIGNMENT_DESC_DIR}' does not exist.")
        raise FileNotFoundError(f"Assignment descriptions directory '{ASSIGNMENT_DESC_DIR}' does not exist.")
    if not os.path.exists(LO_DIR):
        logging.error(f"Learning objectives directory '{LO_DIR}' does not exist.")
        raise FileNotFoundError(f"Learning objectives directory '{LO_DIR}' does not exist.")
    if not os.path.exists(NEXT_STEPS_DIR):
        logging.error(f"Next steps directory '{NEXT_STEPS_DIR}' does not exist.")
        raise FileNotFoundError(f"Next steps directory '{NEXT_STEPS_DIR}' does not exist.")
    for path in glob.glob(os.path.join(ASSIGNMENT_DESC_DIR, "*.txt")):
        key = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            descs[key] = f.read().strip()
    for path in glob.glob(os.path.join(LO_DIR, "*.txt")):
        key = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            los[key] = [l.strip() for l in f if l.strip()]
    for path in glob.glob(os.path.join(NEXT_STEPS_DIR, "*.txt")):
        key = os.path.splitext(os.path.basename(path))[0]
        with open(path) as f:
            next[key] = [l.strip() for l in f if l.strip()]
    return descs, los, next


def derive_assignment_id(file_name: str) -> str:
    # strip directory + extension
    return os.path.splitext(os.path.basename(file_name))[0]


try:
    ASSIGNMENT_DESCRIPTIONS, LEARNING_OBJECTIVES_MAP, NEXT_STEPS_MAP = load_assignment_resources()
    logging.info(f"Loaded assignment descriptions and learning objectives from directories.")
except Exception as e:
    logging.error(f"Failed to load assignment resources: {e}. Using defaults.")
    ASSIGNMENT_DESCRIPTIONS = {"default": DEFAULT_ASSIGNMENT_DESCRIPTION}
    LEARNING_OBJECTIVES_MAP = {"default": DEFAULT_LEARNING_OBJECTIVES}
    NEXT_STEPS_MAP = {"default": ["No next steps available."]}

app = FastAPI(title="Multi-Agent Flow")

# --- Global variable for experiment config ---
ACTIVE_EXPERIMENT_CONFIG = None # Added

# --- Function to load experiment configuration ---
def load_experiment_config(): # Added
    global ACTIVE_EXPERIMENT_CONFIG
    try:
        with open(EXPERIMENT_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            active_id = config.get("active_experiment_id")
            if active_id and active_id in config.get("experiments", {}):
                ACTIVE_EXPERIMENT_CONFIG = config["experiments"][active_id]
                ACTIVE_EXPERIMENT_CONFIG["id"] = active_id # Store the active experiment ID itself
                logging.info(f"Successfully loaded active A/B experiment config: {active_id}")
            else:
                logging.warning(f"A/B testing: active_experiment_id '{active_id}' not found or invalid in {EXPERIMENT_CONFIG_FILE}. A/B testing disabled.")
                ACTIVE_EXPERIMENT_CONFIG = None
    except FileNotFoundError:
        logging.warning(f"A/B testing: Experiment config file {EXPERIMENT_CONFIG_FILE} not found. A/B testing disabled.")
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
                    message_classification TEXT, -- 'instrumental', 'executive', 'other', or NULL for responses
                    file_name TEXT
                )
            """)
            # Create student profiles table (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id TEXT NOT NULL,
                    file_name TEXT NOT NULL, -- Add file_name column
                    profile_data TEXT NOT NULL, -- Store profile as JSON string
                    PRIMARY KEY (student_id, file_name) -- Composite key
                )
            """)
            # Create student experiment assignments table (if not exists) - Added
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_experiment_assignments (
                    student_id TEXT NOT NULL,
                    experiment_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (student_id, experiment_id)
                )
            """)
            conn.commit()
            logging.info("Database initialized (chat_history, student_profiles & student_experiment_assignments tables checked/created).")
    except sqlite3.Error as e:
        logging.error(f"Database initialization failed: {e}")
        raise

init_db()
load_experiment_config() # Added: Load experiment config on startup

# --- Data Models ---
class StudentMessage(BaseModel):
    student_id: str
    message_text: str
    processed_logs: Optional[str] = None
    file_name: str
    
# This model defines the response TA sends back to chat_interact
class TutorApiResponse(BaseModel):
    final_response: str

# --- Profile Helper Functions ---
# TODO - Allow customization of profile heuristics
DEFAULT_PROFILE = {
    "total_questions": 0,
    "instrumental_count": 0,
    "executive_count": 0,
    "other_count": 0,
    "last_interaction_timestamp": 0.0,
    "needs_guidance_flag": False, 
    "last_executive_example": None, 
    "last_instrumental_example": None 
}


def get_student_profile(student_id: str, file_name: str) -> dict:
    """Retrieves student profile for a specific file from DB or returns default.

    Attempts to load the profile JSON string from the student_profiles table
    based on the composite key (student_id, file_name). If no profile exists
    or if the stored data is invalid JSON, it returns a default profile structure.

    Args:
        student_id: The unique identifier for the student.
        file_name: The specific file context for the profile.

    Returns:
        A dictionary representing the student's profile, updated with stored
        data if found, otherwise the DEFAULT_PROFILE structure.
    """
    profile = DEFAULT_PROFILE.copy()
    profile["student_id"] = student_id
    profile["file_name"] = file_name 
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            # Query using both student_id and file_name
            cursor.execute("SELECT profile_data FROM student_profiles WHERE student_id = ? AND file_name = ?", (student_id, file_name))
            result = cursor.fetchone()
            if result:
                try:
                    stored_profile = json.loads(result[0])
                    profile.update(stored_profile)
                    logging.debug(f"Loaded profile for {student_id} (file: {file_name})")
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode profile JSON for {student_id} (file: {file_name}). Using default.")
            else:
                logging.debug(f"No profile found for {student_id} (file: {file_name}). Using default.")
    except sqlite3.Error as e:
        logging.error(f"DB error getting profile for {student_id} (file: {file_name}): {e}. Using default.")
    return profile

def update_student_profile_sync(student_id: str, file_name: str, classification: str, timestamp: float, question_text: str):
    """Updates profile counts, flags, and example questions for a specific file."""
    logging.info(f"Background task: Updating profile for {student_id} (file: {file_name}) based on classification: {classification}")
    try:
        profile = get_student_profile(student_id, file_name)

        # Update counts
        profile["total_questions"] = profile.get("total_questions", 0) + 1
        if classification == "instrumental":
            profile["instrumental_count"] = profile.get("instrumental_count", 0) + 1
            profile["last_instrumental_example"] = question_text 
        elif classification == "executive":
            profile["executive_count"] = profile.get("executive_count", 0) + 1
            profile["last_executive_example"] = question_text 
        else:
            profile["other_count"] = profile.get("other_count", 0) + 1

        # Update timestamp
        profile["last_interaction_timestamp"] = timestamp

        # Update heuristic flag
        non_other_total = profile["instrumental_count"] + profile["executive_count"]
        if non_other_total > 5 and profile["executive_count"] / non_other_total > 0.6:
             if not profile.get("needs_guidance_flag", False): 
                 logging.info(f"Profile update for {student_id}: Setting needs_guidance_flag to True.")
             profile["needs_guidance_flag"] = True
        else:
             if profile.get("needs_guidance_flag", False): 
                 logging.info(f"Profile update for {student_id}: Setting needs_guidance_flag to False.")
             profile["needs_guidance_flag"] = False 

        # Save updated profile back to DB
        if profile.get("last_instrumental_example") and len(profile["last_instrumental_example"]) > 500:
            profile["last_instrumental_example"] = profile["last_instrumental_example"][:500] + "..."
        if profile.get("last_executive_example") and len(profile["last_executive_example"]) > 500:
            profile["last_executive_example"] = profile["last_executive_example"][:500] + "..."

        profile_json = json.dumps(profile)
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO student_profiles (student_id, file_name, profile_data)
                VALUES (?, ?, ?)
            """, (student_id, file_name, profile_json))
            conn.commit()
            logging.info(f"Successfully updated profile for {student_id} (file: {file_name})")

    except sqlite3.Error as e:
        logging.error(f"DB error updating profile for {student_id} (file: {file_name}): {e}")
    except Exception as e:
        logging.error(f"Unexpected error updating profile for {student_id} (file: {file_name}): {e}", exc_info=True)


# --- Helper Functions ---
def get_or_assign_experiment_group(student_id: str) -> Optional[dict]:
    if not ACTIVE_EXPERIMENT_CONFIG or not ACTIVE_EXPERIMENT_CONFIG.get("groups"):
        return None # A/B testing disabled or no groups defined

    experiment_id = ACTIVE_EXPERIMENT_CONFIG["id"]
    groups = ACTIVE_EXPERIMENT_CONFIG["groups"]
    num_groups = len(groups)

    if num_groups == 0:
        logging.warning(f"A/B testing: No groups defined for experiment {experiment_id}.")
        return None

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
                        logging.info(f"Student {student_id} already in group '{assigned_group_id}' for experiment '{experiment_id}'.")
                        return group # Return the full group object
                logging.warning(f"Student {student_id} assigned to group '{assigned_group_id}' but group not found in current config for experiment '{experiment_id}'. Using default.")
                return groups[0] # Fallback to first group if stored group_id is somehow invalid

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

    except sqlite3.Error as e:
        logging.error(f"Database error during experiment group assignment for {student_id}: {e}")
        # Fallback to a default group (e.g., the first one) in case of DB error to ensure functionality
        return groups[0] if groups else None
    except Exception as e:
        logging.error(f"Unexpected error during experiment group assignment for {student_id}: {e}")
        return groups[0] if groups else None


def select_learning_objective_embeddings(question_text: str, learning_objectives: list) -> str:
    """Selects the most relevant LO using sentence embeddings."""
    if not embedding_model or LO_EMBEDDINGS is None:
        logging.error("Sentence Transformer model or LO embeddings not available. Falling back to first LO.")
        return "No specific LO"

    try:
        question_embedding = embedding_model.encode(question_text, convert_to_tensor=True)

        # Compute cosine similarities
        cosine_scores = util.cos_sim(question_embedding, LO_EMBEDDINGS)[0] 

        # Find the index of the highest score
        best_match_idx = torch.argmax(cosine_scores).item()
        best_score = cosine_scores[best_match_idx].item()

        SIMILARITY_THRESHOLD = 0.4

        if best_score >= SIMILARITY_THRESHOLD:
            selected_lo = learning_objectives[best_match_idx]
            logging.info(f"Matched LO (Embeddings) '{selected_lo}' with score {best_score:.4f}")
            return selected_lo
        else:
            # Fallback if no score is high enough (optional, could return best match regardless)
            logging.warning(f"No strong embedding match found (best score: {best_score:.4f}). Defaulting.")
            return learning_objectives[best_match_idx]

    except Exception as e:
        logging.error(f"Error during embedding similarity calculation: {e}")
        return "No specific LO"

def extract_session_id_from_filename(file_name: str, student_id: str) -> str:
    sanitized_file_name = re.sub(r'[^a-zA-Z0-9_]', '', file_name.replace(".chat", "").lower())
    sanitized_student_id = re.sub(r'[^a-zA-Z0-9_]', '', student_id.lower())
    session_id = f"{sanitized_student_id}_{sanitized_file_name}"
    return session_id


async def call_llm(messages: list, model_name: str, purpose: str = "LLM call") -> str: 
    """Calls WebUI's OpenAI-compatible API with a specific model."""
    # WebUI is preferred for LLM calls with API key, but Ollama is also supported
    if WEBUI_API_KEY == "":
        logging.warning("No WebUI API key provided. Defaulting to Ollama API.")
        target_url = f"{OLLAMA_API_BASE}/v1/chat/completions"
        headers={"Content-Type": "application/json",
                 "Accept": "application/json"
            }
        logging.debug(f"Calling Ollama ({model_name}) for {purpose} at {target_url}: {messages}")
    else:
        # Use WebUI API
        logging.info(f"Using WebUI API for LLM calls.")
        target_url = f"{WEBUI_API_BASE}/api/chat/completions"
        headers={"Content-Type": "application/json", 
            "Accept": "application/json",
            "Authorization": f"Bearer {WEBUI_API_KEY}"
            }
        logging.debug(f"Calling WebUI ({model_name}) for {purpose} at {target_url}: {messages}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                target_url,
                headers=headers,
                # Use the passed model_name in the payload
                json={"model": model_name, "messages": messages, "stream": False},
                timeout=90
            )
            response.raise_for_status()
            result = response.json()
            logging.debug(f"WebUI Raw Response for {purpose} ({model_name}): {result}")
            if "choices" in result and len(result["choices"]) > 0 and "message" in result["choices"][0] and "content" in result["choices"][0]["message"]:
                 response_text = result["choices"][0]["message"]["content"].strip()
                 logging.info(f"WebUI call successful for {purpose} ({model_name}).")
                 return response_text
            else:
                logging.error(f"Unexpected WebUI response format for {purpose} ({model_name}): {result}")
                raise HTTPException(status_code=500, detail=f"Unexpected response format from LLM for {purpose}.")
    except httpx.RequestError as e:
        logging.error(f"WebUI request failed for {purpose} ({model_name}): {e}")
        raise HTTPException(status_code=503, detail=f"Could not connect to WebUI at {WEBUI_API_BASE}: {e}")
    except httpx.HTTPStatusError as e:
        # (Error handling for status codes remains the same)
        status_code = e.response.status_code
        try: response_detail = e.response.json().get("error", e.response.text[:200])
        except json.JSONDecodeError: response_detail = e.response.text[:200]
        log_message = f"WebUI ({model_name}) returned error status {status_code} for {purpose}: {response_detail}"
        error_detail = f"WebUI error {status_code}: {response_detail}"
        if status_code == 301:
            redirect_location = e.response.headers.get('Location', 'N/A')
            log_message += f" (Redirect detected to: {redirect_location}. Check WEBUI_API_BASE)"
            error_detail += f" (Possible URL misconfiguration, redirect: {redirect_location})"
        logging.error(log_message)
        raise HTTPException(status_code=status_code, detail=error_detail)
    except Exception as e:
        logging.error(f"An unexpected error occurred during WebUI call for {purpose} ({model_name}): {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during {purpose}: {e}")


# --- Database Functions ---
def add_to_history(student_id: str, message_type: str, message_text: str, message_classification: Optional[str] = None, file_name: Optional[str] = None):
    """	
    Adds a message to the chat history in the database.
    """
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_history (student_id, timestamp, message_type, message_text, message_classification, file_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, time.time(), message_type, message_text, message_classification, file_name))
            conn.commit()
            logging.info(f"Added to history: {student_id}, {message_type}, file: {file_name}")
    except sqlite3.Error as e:
        logging.error(f"Failed to add message to history: {e}")

def get_history(student_id: str, file_name: str, limit: int = 6) -> List[dict]: # Added file_name parameter
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

            # Convert to the required {"role": ..., "content": ...} format
            for row in history_rows:
                 role = "user" if row["message_type"] == "question" else "assistant"
                 content = row["message_text"]
                 history_for_llm.append({"role": role, "content": content})

            logging.info(f"Retrieved and formatted {len(history_for_llm)} history entries for {student_id} (file: {file_name}).") 
    except sqlite3.Error as e:
        logging.error(f"Failed to retrieve/format history for {student_id} (file: {file_name}): {e}") 
    return history_for_llm

def format_history_for_prompt(history_messages: list) -> str:
    """Formats a list of message dicts (from get_history, which are {'role': ..., 'content': ...}) into a simple string."""
    if not history_messages:
        return "No recent conversation history."

    formatted_string = "Recent Conversation History:\n"
    for msg in history_messages:
        role = "Student" if msg.get("role") == "user" else "Juno"
        content = msg.get("content", "[message unavailable]")
        formatted_string += f"{role}: {content}\n"
    return formatted_string.strip()


# --- Background Task Function ---
async def classify_and_update_profile(student_id: str, file_name: str, question_text: str, timestamp: float):
    """Background task to classify a question and update the student profile."""
    logging.info(f"Background task started: Classify and update profile for {student_id}")
    classification_result = "other" # Default classification
    try:
        # Load classification prompt from file
        try:
            with open(CLASSIFICATION_PROMPT_FILE, 'r') as f:
                classification_system_prompt = f.read()
        except Exception as e:
            logging.error(f"Background task: Failed to load classification prompt: {e}. Using default.")
            classification_system_prompt = DEFAULT_CLASSIFICATION_PROMPT

        try:    
            with open(POSSIBLE_CLASSIFICATIONS_FILE, 'r') as f:
                POSSIBLE_CLASSIFICATIONS = [line.strip().lower() for line in f if line.strip()]
            if not POSSIBLE_CLASSIFICATIONS: 
                raise ValueError("Classification options file is empty or contains only whitespace.")
            logging.info(f"Loaded {len(POSSIBLE_CLASSIFICATIONS)} classification options from {POSSIBLE_CLASSIFICATIONS_FILE}")
        except Exception as e:
            logging.error(f"Background task: Failed to load classification options: {e}. Using default.")
            POSSIBLE_CLASSIFICATIONS = DEFAULT_POSSIBLE_CLASSIFICATIONS

        classification_prompt_messages = [
            {"role": "system", "content": classification_system_prompt},
            {"role": "user", "content": f"Classify: {question_text}"}
        ]
        # Call LLM for classification
        raw_classification = await call_llm(
            classification_prompt_messages,
            model_name=CLASSIFICATION_MODEL_NAME,
            purpose="background classification"
        )
        clean_classification = raw_classification.strip().lower()
        if clean_classification in POSSIBLE_CLASSIFICATIONS:
            classification_result = clean_classification
        else:
            logging.warning(f"Background task: Unexpected classification '{raw_classification}'. Using default '{classification_result}'.")

    except Exception as e:
        logging.error(f"Background task: Classification LLM call failed for {student_id}: {e}. Using default '{classification_result}'.")

    # Update profile using the synchronous function
    try:
        update_student_profile_sync(student_id, file_name, classification_result, timestamp, question_text)
    except Exception as e:
        logging.error(f"Background task: Failed during update_student_profile_sync for {student_id}: {e}", exc_info=True)

    logging.info(f"Background task finished for {student_id}")


# --- API Endpoints ---
@app.post("/receive_student_message", response_model=TutorApiResponse)
async def receive_student_message(message: StudentMessage, background_tasks: BackgroundTasks):
    """
    Handles incoming student messages:
    1. Classifies the question type (instrumental/executive/other)
    2. Calls EA directly with context (history, logs, LO, assignment, question).
    3. Formulates pedagogical response using LLM + context + EA answer + classification.
    4. Schedules background task for profile update.
    """
    
    # --- A/B Testing: Get student's group and parameters --- Added Block
    student_experiment_group = get_or_assign_experiment_group(message.student_id)
    
    # Default parameters (if A/B test not active or group has no params)
    current_ta_system_prompt_file = TA_SYSTEM_PROMPT_FILE
    current_profile_hint_strategy = "standard" # Default strategy

    if student_experiment_group and "params" in student_experiment_group:
        group_params = student_experiment_group["params"]
        current_ta_system_prompt_file = group_params.get("system_prompt_file", TA_SYSTEM_PROMPT_FILE)
        current_profile_hint_strategy = group_params.get("profile_hint_strategy", "standard")
        logging.info(f"A/B Test: Student {message.student_id} in group '{student_experiment_group['group_id']}'. Using prompt file '{current_ta_system_prompt_file}' and hint strategy '{current_profile_hint_strategy}'.")
    else:
        logging.info(f"A/B Test: No specific group or params for student {message.student_id}. Using default TA prompt and hint strategy.")
    # --- End A/B Testing Block ---

    if message.message_text.strip().lower() == "/report":
        """
        Generates a performance report for the student based on their recent activity logs and conversation history.
        """
        assignment_id = derive_assignment_id(message.file_name)
        assignment_desc = ASSIGNMENT_DESCRIPTIONS.get(assignment_id, DEFAULT_ASSIGNMENT_DESCRIPTION)
        learning_objs = LEARNING_OBJECTIVES_MAP.get(assignment_id, DEFAULT_LEARNING_OBJECTIVES)
        next_steps = NEXT_STEPS_MAP.get(assignment_id, ["Proceed to next assignment.", "Ask Juno for exercises."])
        
        history_msgs = get_history(message.student_id, message.file_name, limit=50)
        hist_str = format_history_for_prompt(history_msgs)
        logs_ctx = message.processed_logs or "No activity logs."
      
        report_prompt = [
            {"role":"system", "content":
                """You are Juno, an automated coach.  
                Using the student's recent notebook logs, conversation history and the assignment's learning objectives, produce a clear performance report for the student. 
                For each learning objective, note strengths, weaknesses, and concrete next steps. 
                Based on the report, suggest a personalized next step for the student.
                Use an encouraging tone, and avoid technical jargon.
                """},
            {"role":"user", "content": f"""
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
        report = await call_llm(
            report_prompt,
            model_name=RESPONSE_MODEL_NAME,
            purpose="performance report generation"
        )
        return TutorApiResponse(final_response=report)
    
    start_time = time.time()
    current_timestamp = time.time()
    logging.info(f"TA received message from {message.student_id} (file: {message.file_name}): '{message.message_text[:100]}...'")

    # --- 0. Get Context ---
    student_profile = get_student_profile(message.student_id, message.file_name)
    needs_guidance = student_profile.get("needs_guidance_flag", False)
    last_exec_example = student_profile.get("last_executive_example")
    last_instr_example = student_profile.get("last_instrumental_example")
    logging.info(f"Retrieved profile for {message.student_id}: Guidance Flag = {needs_guidance}")

    conversation_history_messages = get_history(message.student_id, message.file_name, limit=6)
    formatted_history_for_ea = format_history_for_prompt(conversation_history_messages)

    # --- Extract Processed Logs ---
    logs_context = "No recent activity logs available."
    if message.processed_logs and message.processed_logs.strip():
        logs_context = message.processed_logs.strip()
        logging.info(f"Received processed logs context: '{logs_context[:100]}...'")
    else:
        logging.info("No processed logs provided or logs were empty.")

    assignment_id = derive_assignment_id(message.file_name)
    assignment_description = ASSIGNMENT_DESCRIPTIONS.get(
        assignment_id,
        DEFAULT_ASSIGNMENT_DESCRIPTION
    )
    learning_objectives = LEARNING_OBJECTIVES_MAP.get(
        assignment_id,
        DEFAULT_LEARNING_OBJECTIVES
    )

    # Default values
    ea_response = "The expert agent could not provide an answer."
    final_response = "I'm sorry, I encountered an issue processing your request. Please try again."
    classification_result = "other"  # Default classification

    try:
        # --- 1. Select Learning Objective ---
        learning_objective = select_learning_objective_embeddings(message.message_text, learning_objectives)
        logging.info(f"Selected LO: {learning_objective}")

        # --- 2. Store Current Question ---
        add_to_history(
            student_id=message.student_id, message_type="question",
            message_text=message.message_text, message_classification=None,
            file_name=message.file_name
        )

        # --- 3. Parallel Classification of Question and EA Call ---
        async def classify_question():
            try:
                with open(CLASSIFICATION_PROMPT_FILE, 'r') as f:
                    classification_system_prompt = f.read()
            except Exception as e:
                logging.error(f"Failed to load classification prompt: {e}. Using default.")
                classification_system_prompt = DEFAULT_CLASSIFICATION_PROMPT

            try:    
                with open(POSSIBLE_CLASSIFICATIONS_FILE, 'r') as f:
                    POSSIBLE_CLASSIFICATIONS = [line.strip().lower() for line in f if line.strip()]
                if not POSSIBLE_CLASSIFICATIONS: 
                    raise ValueError("Classification options file is empty or contains only whitespace.")
                logging.info(f"Loaded {len(POSSIBLE_CLASSIFICATIONS)} classification options")
            except Exception as e:
                logging.error(f"Failed to load classification options: {e}. Using default.")
                POSSIBLE_CLASSIFICATIONS = DEFAULT_POSSIBLE_CLASSIFICATIONS

            classification_prompt_messages = [
                {"role": "system", "content": classification_system_prompt},
                {"role": "user", "content": f"Classify: {message.message_text}"}
            ]
            
            try:
                raw_classification = await call_llm(
                    classification_prompt_messages,
                    model_name=CLASSIFICATION_MODEL_NAME,
                    purpose="question classification"
                )
                clean_classification = raw_classification.strip().lower()
                if clean_classification in POSSIBLE_CLASSIFICATIONS:
                    return clean_classification
                else:
                    logging.warning(f"Unexpected classification '{raw_classification}'. Using default 'other'.")
                    return "other"
            except Exception as e:
                logging.error(f"Classification failed: {e}. Using default 'other'.")
                return "other"

        async def call_expert_agent():
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
                logging.info(f"Calling EA at {EA_URL} with direct context for session {session_id}")
                logging.debug(f"EA Payload: {ea_payload}")

                async with httpx.AsyncClient() as client:
                    ea_api_response = await client.post(
                        EA_URL,
                        json=ea_payload,
                        timeout=30
                    )
                    ea_api_response.raise_for_status()
                    return ea_api_response.json()["response"]
            except Exception as e:
                logging.error(f"EA call failed: {e}. Using default EA response.")
                return "The expert agent could not provide an answer."

        # Run classification and EA call in parallel
        classification_task = asyncio.create_task(classify_question())
        ea_task = asyncio.create_task(call_expert_agent())
        
        # Wait for both tasks to complete
        classification_result = await classification_task
        ea_response = await ea_task
        
        logging.info(f"Question classified as: {classification_result}")
        logging.info(f"EA response received: '{ea_response[:100]}...'")

        # --- 4. LLM Call: Formulate Pedagogical Response ---
        try:
            try:
                with open(current_ta_system_prompt_file, 'r') as f:
                    system_prompt_content = f.read()
            except Exception as e:
                logging.error(f"Failed to load TA system prompt from '{current_ta_system_prompt_file}': {e}. Using default.")
                system_prompt_content = DEFAULT_TA_SYSTEM_PROMPT

            # Get current question classification and profile info
            consecutive_executive = student_profile.get("consecutive_executive_count", 0)
            last_classification = student_profile.get("last_question_classification")

            # Apply adaptive response logic based on A/B test group and question type
            if current_profile_hint_strategy == "enhanced_guidance":
                # Treatment group gets adaptive help-seeking logic
                if classification_result == "instrumental":
                    if last_classification == "executive":
                        # Shift from executive to instrumental - provide positive reinforcement
                        system_prompt_content += """\n**Profile Hint (Positive Reinforcement):** The student has shifted from an executive to an instrumental question. Provide explicit positive reinforcement for this shift (e.g., "That's a very effective way to ask for help to understand the material.") along with standard JIT support."""
                        logging.info(f"Adaptive Logic: Detected shift from executive to instrumental for {message.student_id}")
                    else:
                        # Ongoing instrumental questions - maintain standard support
                        system_prompt_content += """\n**Profile Hint (Standard Support):** Continue providing JIT support with a positive and encouraging tone, but without explicit praise. The primary reinforcement is the answer itself."""
                        logging.info(f"Adaptive Logic: Ongoing instrumental questions for {message.student_id}")

                elif classification_result == "executive":
                    # Incremental hints based on consecutive executive questions
                    if consecutive_executive == 1:
                        system_prompt_content += """\n**Profile Hint (First Executive):** This is the first executive question in sequence. Gently guide the student towards reflection, without requiring direct rephrasing. For example: "That question seems focused on getting the answer directly. For the following questions, can you think about how to rephrase them to better understand the underlying concepts?"""
                        logging.info(f"Adaptive Logic: First executive question for {message.student_id}")
                    elif consecutive_executive == 2:
                        system_prompt_content += """\n**Profile Hint (Second Executive):** This is the second consecutive executive question. Provide elements of good instrumental questions. For example: "Good questions often explore the 'why' or 'how' of a concept, or compare different approaches. How might you rephrase following questions with that in mind?" or "Good questions decompose complex concepts into smaller, more manageable parts. How might you rephrase following questions with that in mind?""""
                        logging.info(f"Adaptive Logic: Second consecutive executive question for {message.student_id}")
                    elif consecutive_executive == 3:
                        system_prompt_content += """\n**Profile Hint (Third Executive):** This is the third consecutive executive question. Take an example and rephrase it as a model instrumental question. For example: "If you asked '[student's executive question example]', a better version might be '[rephrased instrumental question]'. Could you try rephrasing your next request similarly?"""
                        logging.info(f"Adaptive Logic: Third consecutive executive question for {message.student_id}")
                    else:
                        system_prompt_content += """\n**Profile Hint (Fourth+ Executive):** This is the fourth or subsequent consecutive executive question. Directly refer to the pedagogical rationale. For example: "Research in learning suggests that asking questions focused on understanding is more strongly linked to better learning outcomes than seeking direct solutions. It might be helpful to try and focus on understanding the process here." or "Focusing on direct solutions is not as effective as asking questions that help you understand the material. How might you rephrase your next request to focus on understanding the material?""""
                        logging.info(f"Adaptive Logic: Fourth+ consecutive executive question for {message.student_id}")
            elif current_profile_hint_strategy == "none":
                # Control group gets no adaptive hints
                logging.info(f"Control group: No adaptive hints for {message.student_id}")
                pass
            else:
                logging.warning(f"Unknown profile hint strategy '{current_profile_hint_strategy}' for {message.student_id}")

            system_prompt_content += "\n" 

            final_prompt_messages = []
            final_prompt_messages.append({"role": "system", "content": system_prompt_content})
            if conversation_history_messages:
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

                    Based on the context above (including profile hints and history), formulate your response as Juno, focusing directly on answering or guiding the student regarding their specific question. Never reveal or mention internal information like learning objectives or the expert source."""
                }
            )

            final_response = await call_llm(
                final_prompt_messages,
                model_name=RESPONSE_MODEL_NAME,
                purpose="final pedagogical response formulation"
            )
            logging.info(f"Final formulated response: '{final_response[:100]}...'")

        except Exception as e:
            logging.error(f"LLM Call (Pedagogical Response) failed: {e}. Using default final response.")

        # --- 5. Store Final Response ---
        add_to_history(
            student_id=message.student_id, message_type="response",
            message_text=final_response, message_classification=None,
            file_name=message.file_name
        )

        # --- 6. Schedule Background Task for Profile Update ---
        background_tasks.add_task(
            update_student_profile_sync,
            message.student_id,
            message.file_name, 
            classification_result,
            current_timestamp,
            message.message_text
        )
        logging.info(f"Scheduled background task: update_student_profile_sync for {message.student_id}")

        # --- 7. Return Final Response ---
        processing_time = time.time() - start_time
        logging.info(f"TA processing complete for {message.student_id} in {processing_time:.2f}s. Returning response.")
        return TutorApiResponse(final_response=final_response)

    except Exception as e:
        logging.error(f"Unexpected error in TA handler for {message.student_id}: {e}", exc_info=True)
        return TutorApiResponse(final_response="I'm sorry, an error occurred while processing your request.")


@app.get("/verify_ta")
def verify():
    return {"message": "Tutor Agent (Sync Response) is working"}

# Load model (do this once at startup, outside the request handler)
# Use a lightweight model suitable for the task
try:
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device=device)
    logging.info(f"Sentence Transformer model loaded successfully on {device}.")
    LO_EMBEDDINGS = embedding_model.encode(LEARNING_OBJECTIVES_MAP.get("default", DEFAULT_LEARNING_OBJECTIVES), convert_to_tensor=True)
    logging.info("Pre-computed embeddings for Learning Objectives.")
except Exception as e:
    logging.error(f"Failed to load Sentence Transformer model or encode LOs: {e}")
    embedding_model = None
    LO_EMBEDDINGS = None

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)