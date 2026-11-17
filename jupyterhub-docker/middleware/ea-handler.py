# ea_handler.py (LLM-powered Expert Agent)
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import logging
import uvicorn
from dotenv import load_dotenv

# --- Configuration ---
load_dotenv() # Load environment variables from .env file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - EA - %(message)s')

import llm_client
from config_loader import section, model_override, read_input

EA_SYSTEM_PROMPT_DEFAULT = """You are an Expert Agent (EA). Your primary role is to provide concise, factual, technical information ONLY in direct response to the specific 'Student Question' provided, using the Assignment, LO, History, and Logs as context.
"""

logging.info(f"EA LLM settings: {llm_client.get_settings().describe()}")

app = FastAPI(title="Expert Agent (LLM-Powered)")

class ExpertQueryPayload(BaseModel):
    student_question: str
    assignment_description: str
    learning_objective: str
    history: str # Expecting the formatted string from TA
    logs: str
    session_id: str

# --- LLM Calling Helper ---
async def call_ea_llm(messages: list) -> str:
    """Calls the configured OpenAI-compatible LLM with the model of the expert role."""
    try:
        return await llm_client.call_llm(messages, role="expert", model=model_override("expert"), purpose="expert answer")
    except llm_client.LLMError as e:
        logging.error(str(e))
        raise HTTPException(status_code=e.status_code or 500, detail=str(e))


@app.post("/expert_query")
async def expert_query(payload: ExpertQueryPayload): # Use the updated payload model
    """
    Receives context from the TA, calls an LLM for a technical answer,
    and returns the concise response, handling vague questions appropriately.
    """
    logging.info(f"Received query for session {payload.session_id}. Student Question: '{payload.student_question[:150]}...'")

    # --- Load EA System Prompt ---
    prompt_file = section("prompts").get("expert_system_file", "ea_system_prompt.txt")
    ea_system_prompt = read_input(prompt_file, EA_SYSTEM_PROMPT_DEFAULT)

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