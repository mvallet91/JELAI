# ea_handler.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
import logging
import uvicorn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - EA - %(message)s')

app = FastAPI(title="Fake Expert Agent")

class ExpertQuery(BaseModel):
    prompt: str
    session_id: str 

@app.post("/expert_query")
async def expert_query(query: ExpertQuery):
    """
    Receives a prompt from the TA and returns a fixed response.
    """
    logging.info(f"Received query for session {query.session_id}. Prompt: '{query.prompt[:100]}...'") 
    fake_response = "You need to use pandas"
    logging.info(f"Returning fake response: '{fake_response}'")
    return {"response": fake_response}

@app.get("/verify_ea")
def verify():
    return {"message": "Fake EA is working"}

if __name__ == "__main__":
    # Runs on port 8003
    uvicorn.run(app, host="0.0.0.0", port=8003)