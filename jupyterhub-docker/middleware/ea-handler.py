# ea_handler.py (LLM-powered Expert Agent)
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import logging
import uvicorn
import httpx
import os
import json
from dotenv import load_dotenv
from typing import Optional # Added Optional

# --- Configuration ---
load_dotenv() # Load environment variables from .env file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - EA - %(message)s')

# LLM Configuration (similar to TA)
WEBUI_API_BASE = os.getenv("webui_url", "http://localhost:3000") # Your WebUI URL
WEBUI_API_KEY = os.getenv("webui_api_key", "")
OLLAMA_API_BASE = os.getenv("ollama_url", "http://localhost:11434") # Ollama API URL
# Use a specific model for EA if defined, otherwise fallback to a default
EA_MODEL_NAME = os.getenv("ollama_ea_model", "gemma3:4b") # Model for EA tasks
# Define path for EA system prompt (relative to where ea-handler.py is run)
EA_SYSTEM_PROMPT_FILE = "./inputs/ea_system_prompt.txt"

# --- Updated EA System Prompt ---
EA_SYSTEM_PROMPT_DEFAULT = """You are an Expert Agent (EA). Your primary role is to provide concise, factual, technical information ONLY in direct response to the specific 'Student Question' provided, using the Assignment, LO, History, and Logs as context.
"""

logging.info(f"EA Using WebUI Base URL: {WEBUI_API_BASE}")
logging.info(f"EA Using Model: {EA_MODEL_NAME}")

app = FastAPI(title="Expert Agent (LLM-Powered)")

# --- Updated Pydantic Model ---
class ExpertQueryPayload(BaseModel): # Renamed and updated model
    student_question: str
    assignment_description: str
    learning_objective: str
    history: str # Expecting the formatted string from TA
    logs: str
    session_id: str

# --- LLM Calling Helper ---
async def call_ea_llm(messages: list) -> str:
    """Calls the configured LLM API (WebUI or Ollama) for the EA."""
    if WEBUI_API_KEY == "":
        logging.warning("EA: No WebUI API key provided. Defaulting to Ollama API.")
        target_url = f"{OLLAMA_API_BASE}/v1/chat/completions"
        headers={"Content-Type": "application/json", "Accept": "application/json"}
        logging.debug(f"EA Calling Ollama ({EA_MODEL_NAME}) at {target_url}")
    else:
        logging.info(f"EA Using WebUI API for LLM calls.")
        target_url = f"{WEBUI_API_BASE}/api/chat/completions"
        headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": f"Bearer {WEBUI_API_KEY}"}
        logging.debug(f"EA Calling WebUI ({EA_MODEL_NAME}) at {target_url}")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                target_url,
                headers=headers,
                json={"model": EA_MODEL_NAME, "messages": messages, "stream": False},
                timeout=60 # Slightly shorter timeout for EA might be okay
            )
            response.raise_for_status()
            result = response.json()
            logging.debug(f"EA Raw LLM Response: {result}")
            if "choices" in result and len(result["choices"]) > 0 and "message" in result["choices"][0] and "content" in result["choices"][0]["message"]:
                 response_text = result["choices"][0]["message"]["content"].strip()
                 logging.info(f"EA LLM call successful.")
                 return response_text
            else:
                logging.error(f"EA Unexpected LLM response format: {result}")
                raise HTTPException(status_code=500, detail="EA: Unexpected response format from LLM.")
    except httpx.RequestError as e:
        logging.error(f"EA LLM request failed: {e}")
        raise HTTPException(status_code=503, detail=f"EA: Could not connect to LLM service: {e}")
    except httpx.HTTPStatusError as e:
        status_code = e.response.status_code
        try: response_detail = e.response.json().get("error", e.response.text[:200])
        except json.JSONDecodeError: response_detail = e.response.text[:200]
        logging.error(f"EA LLM returned error status {status_code}: {response_detail}")
        raise HTTPException(status_code=status_code, detail=f"EA LLM error {status_code}: {response_detail}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during EA LLM call: {e}")
        raise HTTPException(status_code=500, detail=f"EA: An unexpected error occurred during LLM call: {e}")


@app.post("/expert_query")
async def expert_query(payload: ExpertQueryPayload): # Use the updated payload model
    """
    Receives context from the TA, calls an LLM for a technical answer,
    and returns the concise response, handling vague questions appropriately.
    """
    logging.info(f"Received query for session {payload.session_id}. Student Question: '{payload.student_question[:150]}...'")

    # --- Load EA System Prompt ---
    try:
        with open(EA_SYSTEM_PROMPT_FILE, "r") as f:
            ea_system_prompt = f.read().strip()
        if not ea_system_prompt:
            raise FileNotFoundError # Treat empty file as not found
        logging.info(f"Loaded EA system prompt from {EA_SYSTEM_PROMPT_FILE}")
    except FileNotFoundError:
        logging.warning(f"EA System prompt file not found at {EA_SYSTEM_PROMPT_FILE} or empty. Using default prompt.")
        ea_system_prompt = EA_SYSTEM_PROMPT_DEFAULT
    except Exception as e:
        logging.error(f"Error loading EA system prompt from {EA_SYSTEM_PROMPT_FILE}: {e}. Using default.")
        ea_system_prompt = EA_SYSTEM_PROMPT_DEFAULT

    # --- Construct Prompt for EA's internal LLM using payload fields ---
    prompt_context = f"""[INTERNAL CONTEXT]
    Assignment: {payload.assignment_description}
    Task Objective: {payload.learning_objective}
    Recent Logs:
    {payload.logs}

    Conversation History:
    {payload.history}
    [END INTERNAL CONTEXT]

    Student Question: {payload.student_question}

    ---
    Based *only* on the 'Student Question' above and using the other information strictly as context, provide the concise technical information needed. If the question is not a specific technical query, follow the instructions in your system prompt precisely.
    """

    ea_llm_messages = [
        {"role": "system", "content": ea_system_prompt},
        {"role": "user", "content": prompt_context}
    ]
    logging.debug(f"EA LLM Messages: {ea_llm_messages}")

    # --- Call EA's internal LLM ---
    try:
        llm_response = await call_ea_llm(ea_llm_messages)
        logging.info(f"EA LLM generated response for session {payload.session_id}: '{llm_response[:100]}...'")
        return {"response": llm_response} # Return in the format TA expects
    except HTTPException as e:
        # Re-raise HTTPExceptions from the LLM call to inform the TA
        raise e
    except Exception as e:
        # Catch any other unexpected errors during processing
        logging.error(f"Error processing expert query after LLM call setup for session {payload.session_id}: {e}", exc_info=True)
        # Return a generic error response to the TA
        raise HTTPException(status_code=500, detail="Expert Agent encountered an internal error processing the request.")


@app.get("/verify_ea")
def verify():
    # You might want to add a check here to see if the LLM endpoint is reachable
    return {"message": "Expert Agent (LLM-Powered) is running"}

if __name__ == "__main__":
    # Runs on port 8003
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)