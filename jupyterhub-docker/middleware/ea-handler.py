# ea_handler.py (LLM-powered Expert Agent)
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import logging
import uvicorn
import httpx
import os
import json
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv() # Load environment variables from .env file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - EA - %(message)s')

# LLM Configuration (similar to TA)
WEBUI_API_BASE = os.getenv("webui_url", "http://localhost:3000") # Your WebUI URL
WEBUI_API_KEY = os.getenv("webui_api_key", "")
OLLAMA_API_BASE = os.getenv("ollama_url", "http://localhost:11434") # Ollama API URL
# Use a specific model for EA if defined, otherwise fallback to a default
EA_MODEL_NAME = os.getenv("ollama_ea_model", "gemma3:4b") # Model for EA tasks

logging.info(f"EA Using WebUI Base URL: {WEBUI_API_BASE}")
logging.info(f"EA Using Model: {EA_MODEL_NAME}")

app = FastAPI(title="Expert Agent (LLM-Powered)")

class ExpertQuery(BaseModel):
    prompt: str # This prompt comes structured from the TA
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
async def expert_query(query: ExpertQuery):
    """
    Receives a structured prompt from the TA, calls an LLM for a technical answer,
    and returns the concise response.
    """
    logging.info(f"Received query for session {query.session_id}. TA Prompt: '{query.prompt[:150]}...'")

    # Construct messages for the EA's LLM
    # The system prompt defines the EA's role.
    # The user message IS the prompt received from the TA.
    ea_llm_messages = [
        {"role": "system", "content": """You are an expert in Python programming, data science libraries (like pandas, matplotlib), and general computer science concepts.
        You will receive a structured request containing a student's question, the relevant learning objective (LO), the overall assignment task, and potentially context like recent notebook activity or conversation history.
        Your task is to provide a CONCISE, technically accurate answer or explanation based ONLY on the information provided in the request.
        Focus solely on the technical aspects relevant to the student's question within the given context.
        Do NOT adopt a tutor persona. Do NOT add conversational filler, greetings, or explanations beyond the core technical information needed.
        Do NOT refer to the student directly. Provide only the essential technical facts, code snippets (if applicable and concise), or function names needed to address the core of the student's query.
        Example: If asked how to count items, respond with something like: "Use the `.value_counts()` method on the pandas Series." or "Group by the relevant column using `.groupby()` then apply `.size()` or `.count()`."
        Keep your response brief and factual."""},
        {"role": "user", "content": query.prompt} # Pass the TA's structured prompt directly
    ]

    try:
        llm_response = await call_ea_llm(ea_llm_messages)
        logging.info(f"EA LLM generated response: '{llm_response[:100]}...'")
        return {"response": llm_response}
    except HTTPException as e:
        # Re-raise HTTPExceptions from the LLM call to inform the TA
        raise e
    except Exception as e:
        # Catch any other unexpected errors during processing
        logging.error(f"Error processing expert query after LLM call setup: {e}", exc_info=True)
        # Return a generic error response to the TA
        return {"response": "Expert Agent encountered an internal error."}


@app.get("/verify_ea")
def verify():
    # You might want to add a check here to see if the LLM endpoint is reachable
    return {"message": "Expert Agent (LLM-Powered) is running"}

if __name__ == "__main__":
    # Runs on port 8003
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)