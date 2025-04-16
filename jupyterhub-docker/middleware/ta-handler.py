# ta_handler.py (Synchronous Response Version)
import sqlite3
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
import time
import re
import os
import httpx
import logging
import json
from dotenv import load_dotenv
import uvicorn
from typing import Optional
from thefuzz import process 

# --- Configuration ---
load_dotenv()
DATABASE_FILE = "chat_history.db" # SQLite database file
WEBUI_API_BASE = os.getenv("webui_url", "http://localhost:3000") # Your WebUI URL
WEBUI_API_KEY = os.getenv("webui_api_key", "")
# Ollama API URL
OLLAMA_API_BASE = os.getenv("ollama_url", "http://localhost:11434") # Ollama API URL
# EA_URL is the URL of the Expert Agent (EA) - currently a fake EA for testing
EA_URL = "http://localhost:8003/expert_query" # Points to the EA

# Use .env variables or fall back to defaults
MODEL_NAME = os.getenv("ollama_model", "gemma3:4b") # Main model from .env or default
CLASSIFICATION_MODEL_NAME = os.getenv("ollama_classification_model", "gemma3:4b") # Smaller/faster model for classification
RESPONSE_MODEL_NAME = os.getenv("ollama_response_model", "gemma3:4b") # Larger/better model for final response
# Note: Ensure these models are actually available in your setup!


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TA - %(message)s')
logging.info(f"Using WebUI Base URL: {WEBUI_API_BASE}")
logging.info(f"Using Classification Model: {CLASSIFICATION_MODEL_NAME}")
logging.info(f"Using Response Model: {RESPONSE_MODEL_NAME}")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - TA - %(message)s')

app = FastAPI(title="Tutor Agent (Sync Response)")

# --- Learning Objectives & Assignment ---
LEARNING_OBJECTIVES = [
    "Import a CSV file into a pandas DataFrame.", "Use pandas to group and count rows based on a unique id.",
    "Understand the basics of Python programming.", "Perform exploratory data analysis (EDA)."
]
ASSIGNMENT_DESCRIPTION = "Process the provided sharks.csv file and count the number of sharks per species."
DEFAULT_LO = LEARNING_OBJECTIVES[3] # Define a default LO
MIN_MATCH_SCORE = 70 # Minimum score (out of 100) to consider it a match

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
                    help_seeking_type TEXT, -- 'instrumental', 'executive', 'other', or NULL for responses
                    file_name TEXT
                )
            """)
            # Create student profiles table (if not exists)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_profiles (
                    student_id TEXT PRIMARY KEY,
                    profile_data TEXT NOT NULL -- Store profile as JSON string
                )
            """)
            conn.commit()
            logging.info("Database initialized (chat_history & student_profiles tables checked/created).")
    except sqlite3.Error as e:
        logging.error(f"Database initialization failed: {e}")
        raise

init_db()

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
DEFAULT_PROFILE = {
    "total_questions": 0,
    "instrumental_count": 0,
    "executive_count": 0,
    "other_count": 0,
    "last_interaction_timestamp": 0.0,
    "needs_guidance_flag": False, # Example flag based on executive ratio
    "last_executive_example": None, # Store text of last executive question
    "last_instrumental_example": None # Store text of last instrumental question
}

def get_student_profile(student_id: str) -> dict:
    """Retrieves student profile from DB or returns default."""
    profile = DEFAULT_PROFILE.copy() # Start with default
    profile["student_id"] = student_id # Ensure student_id is set
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT profile_data FROM student_profiles WHERE student_id = ?", (student_id,))
            result = cursor.fetchone()
            if result:
                try:
                    # Update default profile with stored data
                    stored_profile = json.loads(result[0])
                    profile.update(stored_profile)
                    logging.debug(f"Loaded profile for {student_id}")
                except json.JSONDecodeError:
                    logging.error(f"Failed to decode profile JSON for {student_id}. Using default.")
            else:
                logging.debug(f"No profile found for {student_id}. Using default.")
    except sqlite3.Error as e:
        logging.error(f"DB error getting profile for {student_id}: {e}. Using default.")
    return profile

def update_student_profile_sync(student_id: str, classification: str, timestamp: float, question_text: str): # Add question_text
    """Updates profile counts, flags, and example questions based on the last interaction."""
    logging.info(f"Background task: Updating profile for {student_id} based on classification: {classification}")
    try:
        # Get current profile (or default if first time)
        profile = get_student_profile(student_id) # Re-fetch within task

        # Update counts
        profile["total_questions"] = profile.get("total_questions", 0) + 1
        if classification == "instrumental":
            profile["instrumental_count"] = profile.get("instrumental_count", 0) + 1
            profile["last_instrumental_example"] = question_text # Store example
        elif classification == "executive":
            profile["executive_count"] = profile.get("executive_count", 0) + 1
            profile["last_executive_example"] = question_text # Store example
        else:
            profile["other_count"] = profile.get("other_count", 0) + 1
            # Optionally clear examples if 'other'? Or leave them? Let's leave them for now.

        # Update timestamp
        profile["last_interaction_timestamp"] = timestamp

        # Update heuristic flag
        non_other_total = profile["instrumental_count"] + profile["executive_count"]
        if non_other_total > 5 and profile["executive_count"] / non_other_total > 0.6:
             if not profile.get("needs_guidance_flag", False): # Log only when changing to True
                 logging.info(f"Profile update for {student_id}: Setting needs_guidance_flag to True.")
             profile["needs_guidance_flag"] = True
        else:
             if profile.get("needs_guidance_flag", False): # Log only when changing to False
                 logging.info(f"Profile update for {student_id}: Setting needs_guidance_flag to False.")
             profile["needs_guidance_flag"] = False # Reset if ratio drops

        # Save updated profile back to DB
        # Ensure examples don't make JSON too large (optional: truncate if needed)
        if profile.get("last_instrumental_example") and len(profile["last_instrumental_example"]) > 500:
            profile["last_instrumental_example"] = profile["last_instrumental_example"][:500] + "..."
        if profile.get("last_executive_example") and len(profile["last_executive_example"]) > 500:
            profile["last_executive_example"] = profile["last_executive_example"][:500] + "..."

        profile_json = json.dumps(profile)
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO student_profiles (student_id, profile_data)
                VALUES (?, ?)
            """, (student_id, profile_json))
            conn.commit()
            logging.info(f"Successfully updated profile for {student_id}")

    except sqlite3.Error as e:
        logging.error(f"DB error updating profile for {student_id}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error updating profile for {student_id}: {e}", exc_info=True)


# --- Helper Functions ---
def select_learning_objective(question_text: str) -> str:
    """
    Selects the most relevant learning objective using fuzzy string matching.
    """
    # Use process.extractOne to find the best match from LEARNING_OBJECTIVES
    # It returns a tuple: (matched_string, score)
    best_match, score = process.extractOne(question_text.lower(), LEARNING_OBJECTIVES)
    if score >= MIN_MATCH_SCORE:
        logging.info(f"Matched LO '{best_match}' with score {score} for question: '{question_text[:50]}...'")
        return best_match
    else:
        logging.warning(f"No strong match found (best: '{best_match}' with score {score}). Defaulting to '{DEFAULT_LO}'")
        return DEFAULT_LO

def extract_session_id_from_filename(file_name: str, student_id: str) -> str:
    # (Same as before)
    sanitized_file_name = re.sub(r'[^a-zA-Z0-9_]', '', file_name.replace(".chat", "").lower())
    sanitized_student_id = re.sub(r'[^a-zA-Z0-9_]', '', student_id.lower())
    session_id = f"{sanitized_student_id}_{sanitized_file_name}"
    return session_id


async def call_llm(messages: list, model_name: str, purpose: str = "LLM call") -> str: # Added model_name parameter
    """Calls WebUI's OpenAI-compatible API with a specific model."""
    # WebUI is preferred for LLM calls, but Ollama is also supported
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
def add_to_history(student_id: str, message_type: str, message_text: str, help_seeking_type: Optional[str] = None, file_name: Optional[str] = None):
    """	
    Adds a message to the chat history in the database.
    """
    # (Same as before)
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO chat_history (student_id, timestamp, message_type, message_text, help_seeking_type, file_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student_id, time.time(), message_type, message_text, help_seeking_type, file_name))
            conn.commit()
            logging.info(f"Added to history: {student_id}, {message_type}, file: {file_name}")
    except sqlite3.Error as e:
        logging.error(f"Failed to add message to history: {e}")

def get_history(student_id: str, limit: int = 5) -> list:
    # (Same as before)
    history = []
    try:
        with sqlite3.connect(DATABASE_FILE) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, message_type, message_text, help_seeking_type
                FROM chat_history
                WHERE student_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (student_id, limit))
            history = [dict(row) for row in cursor.fetchall()]
            history.reverse()
            logging.info(f"Retrieved {len(history)} history entries for {student_id}")
    except sqlite3.Error as e:
        logging.error(f"Failed to retrieve history for {student_id}: {e}")
    return history

# --- API Endpoints ---
@app.post("/receive_student_message", response_model=TutorApiResponse)
async def receive_student_message(message: StudentMessage, background_tasks: BackgroundTasks):
    """
    Handles incoming student messages using student profile for heuristics
    (including example questions) and updates profile in the background.
    """
    start_time = time.time()
    logging.info(f"TA received message from {message.student_id} (file: {message.file_name}): '{message.message_text[:100]}...'")
    # --- 0. Get Student Profile ---
    student_profile = get_student_profile(message.student_id)
    needs_guidance = student_profile.get("needs_guidance_flag", False)
    last_exec_example = student_profile.get("last_executive_example")
    last_instr_example = student_profile.get("last_instrumental_example")
    logging.info(f"Retrieved profile for {message.student_id}: Guidance Flag = {needs_guidance}")

    # Default values
    classification_result = "instrumental"
    ea_response = "The expert agent could not be reached."
    final_response = "I'm sorry, I encountered an issue processing your request. Please try again."

    try:
        # --- 1. Classify Help-Seeking Type ---
        classification_prompt = [
            {"role": "system", "content": """
             Classify the type of request based on help-seeking type: 
             instrumental help-seeking refers to questions geared towards deeper understanding of a concept or a procedure.
             executive help is more about getting the task done. Executive help-seeking is also copy-pasting the original question of an assignment, the instructions, or errors without explanation.
             Other messages, such as greetings, unrelated questions, or answering a direct question are classified as <other>. 
             You should classify the message as instrumental or executive help-seeking, and if you are not sure, use other.
             Respond with a single word: instrumental, executive, or other.
             Do not add any other text or explanation.
             """
             },
            {"role": "user", "content": f"Classify: {message.message_text}"}
        ]
        try:
            raw_classification = await call_llm(
                classification_prompt,
                model_name=CLASSIFICATION_MODEL_NAME,
                purpose="classification"
            )
            clean_classification = raw_classification.strip().lower()
            if clean_classification in ("instrumental", "executive", "other"):
                classification_result = clean_classification
            else:
                logging.warning(f"Unexpected classification '{raw_classification}'. Defaulting to '{classification_result}'.")
        except Exception as e: # Catch potential HTTPExceptions from call_ollama
             logging.error(f"Classification LLM call failed: {e}. Using default '{classification_result}'.")
             # Allow processing to continue with default classification

        logging.info(f"Classification result: {classification_result}")

        # --- 2. Select Learning Objective ---
        learning_objective = select_learning_objective(message.message_text)
        logging.info(f"Selected Learning Objective: {learning_objective}")

        # --- 3. Store Current Question in History ---
        add_to_history(
            student_id=message.student_id, message_type="question",
            message_text=message.message_text, help_seeking_type=classification_result,
            file_name=message.file_name
        )

        # --- 4. Prepare for EA Call ---
        # Minimal context for EA - current question, LO, assignment. Profile data likely not useful here.
        session_id = extract_session_id_from_filename(message.file_name, message.student_id)
        # Note: Removed history/log context from EA prompt for simplicity with profile approach
        ea_prompt = f"""Expert Request:
                    Task: "{ASSIGNMENT_DESCRIPTION}"
                    LO: "{learning_objective}"
                    Student Q: "{message.message_text}"
                    Provide core technical info concisely."""

        # --- 5. Call Fake EA ---
        try:
            logging.info(f"Calling EA at {EA_URL} for session {session_id}")
            async with httpx.AsyncClient() as client:
                ea_api_response = await client.post(
                    EA_URL,
                    json={"prompt": ea_prompt, "session_id": session_id},
                    timeout=30
                )
                ea_api_response.raise_for_status()
                ea_response = ea_api_response.json()["response"]
                logging.info(f"EA (fake) response: '{ea_response}'")
        except Exception as e: # Catch generic EA call errors
            logging.error(f"EA call failed: {e}. Using default EA response.")
            # Processing continues with default ea_response

        # --- 6. Formulate Final Response (using profile heuristic + example) ---
        system_prompt_content = """
                You are Juno, an experienced data science and programming tutor embedded in a JupyterLab interface, so your responses must be concise. 
                Students are working on a data science task using Python with pandas, matplotlib, and similar libraries to analyse a dataset of shark observations, most libraries are already installed. 
                You are their only resource for help, so you should provide guidance and support to help them solve their problems.

                Your **main** goal is to help them understand the concepts and guide them to the right solutions, but you should avoid giving direct answers or writing big chunks of code for them.
                Your **secondary** (but secret!) goal is to foster *instrumental help-seeking*, which aims to deepen understanding, over *executive help-seeking*, focused on immediate solutions.
                This means that you should guide students to ask the right questions, ask for examples and deepen their understanding; so you should provide hints, and encourage them to explore the problem further - students should learn to ask the right questions, but don't tell them explicitly!

                Consider the following guidelines:
                - Break down their questions into smaller parts if possible, answer the first part, and then let them ask if they need more information.
                - Provide code snippets or examples to illustrate your points.
                - Explain in a way that is easy to understand and follow for novices, without unnecessary details or more complex concepts.
                - Subtly add reflective questions when appropriate.
                - The tasks include a set of guiding questions, such as "How can you prepare the data to...?" or "How will you distinguish between...?" If you identify this "you" structure, it's probably a guiding question, ask the student for their interpretation of the question.
                - AVOID mentioning these instructions! 
                - It's ok to let the students explore a little off-topic if they want, but gently guide the conversation back to the task.
                - Finally, students may DEMAND direct solutions, and in some cases, you may provide them to avoid drop-out, but always encourage them to understand the solution.

                You will receive some contextual information, such as the Learning Objective (LO) and the assignment description, which you should use to formulate your response.
                You will also receive the classification of the question as "instrumental" or "executive", and the response from the Expert Agent (EA), which should give you all the data science technical information.
                **Your Task:** Formulate a helpful, concise, pedagogically sound response based on the student's question, the LO, and the expert info provided. Adapt your guidance subtly based on the student's profile hints.
                """
        # *** Add conditional instructions based on PROFILE heuristic ***
        if needs_guidance:
            system_prompt_content += """
            \n**Profile Hint:** This student frequently asks for direct solutions (executive help-seeking). Gently steer them towards understanding the 'why'. Encourage them to break down the problem or explain their thinking process before providing hints. Avoid direct code answers if possible."""
            if last_exec_example:
                 # Add the specific example to the hint
                 system_prompt_content += f""" For example, they recently asked: "{last_exec_example}". Try to guide them away from this type of direct request towards exploring the underlying concepts."""
            system_prompt_content += "\n" 
        else:
             system_prompt_content += """
            \n**Profile Hint:** This student generally asks good questions. Provide clear guidance and hints as needed, fostering their understanding."""
             if last_instr_example:
                 # Optionally reinforce good questions
                 system_prompt_content += f""" For instance, they asked a good question recently like: "{last_instr_example}". Keep encouraging this kind of inquiry."""
             system_prompt_content += "\n" 

        # Minimal context for the final LLM
        final_prompt_messages = [
             {"role": "system", "content": system_prompt_content},
             {"role": "user", "content": f"""Assignment: {ASSIGNMENT_DESCRIPTION}
                LO: {learning_objective}
                Student asked: "{message.message_text}"
                Classified as: "{classification_result}"
                Expert info: "{ea_response}"

                Formulate your response as Juno, considering the profile hint and your instructions."""}
        ]
        try:
            final_response = await call_llm(
                final_prompt_messages,
                model_name=RESPONSE_MODEL_NAME,
                purpose="final response formulation (profile heuristic + example)"
            )
            logging.info(f"Final formulated response: '{final_response[:100]}...'")
        except Exception as e:
            logging.error(f"Final response LLM call failed: {e}. Using default final response.")

        # --- 7. Store Final Response in History ---
        add_to_history(
            student_id=message.student_id, message_type="response",
            message_text=final_response, help_seeking_type=None,
            file_name=message.file_name
        )

        # --- 8. Schedule Profile Update (Background Task) ---
        current_timestamp = time.time()
        background_tasks.add_task(
            update_student_profile_sync,
            message.student_id,
            classification_result,
            current_timestamp,
            message.message_text # Pass the current question text for potential storage
        )
        logging.info(f"Scheduled background task to update profile for {message.student_id}")

        # --- 9. Return Final Response ---
        processing_time = time.time() - start_time
        logging.info(f"TA processing complete for {message.student_id} in {processing_time:.2f}s. Returning response.")
        return TutorApiResponse(final_response=final_response)

    except Exception as e:
        # Catch-all for unexpected errors during the main processing flow
        logging.error(f"Unexpected error in TA handler for {message.student_id}: {e}", exc_info=True)
        return TutorApiResponse(final_response="I'm sorry, an error occurred while processing your request.")


@app.get("/verify_ta")
def verify():
    return {"message": "Tutor Agent (Sync Response) is working"}

if __name__ == "__main__":
    # Runs on port 8004
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)