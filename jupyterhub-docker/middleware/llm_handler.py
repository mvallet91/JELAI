#!/usr/bin/env python
"""Example of a chat server with persistence handled on the backend."""

import re
import os
import logging
from pathlib import Path
from typing import Callable, Union, Optional, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from langchain_ollama import OllamaLLM as Ollama
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder

# Load environment variables
load_dotenv()
base_url = os.getenv("ollama_url")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize FastAPI application
app = FastAPI(
    title="LangChain Server",
    version="1.0",
    description="Spin up a simple API server using Langchain's Runnable interfaces",
)

# Utility to validate session ID
def _is_valid_identifier(value: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9-_]+$", value))

# Create session factory for chat histories
def create_session_factory(base_dir: Union[str, Path]) -> Callable[[str], FileChatMessageHistory]:
    base_dir_ = Path(base_dir)
    base_dir_.mkdir(parents=True, exist_ok=True)

    def get_chat_history(session_id: str) -> FileChatMessageHistory:
        if not _is_valid_identifier(session_id):
            raise HTTPException(
                status_code=400,
                detail=f"Session ID `{session_id}` is not in a valid format. "
                       "Session ID must only contain alphanumeric characters, hyphens, and underscores.",
            )
        logging.info(f"Loading chat history for session ID: {session_id}")
        return FileChatMessageHistory(base_dir_ / f"{session_id}.json")

    return get_chat_history

# System prompt for the assistant
system_prompt = """
You are Juno, an experienced data science and programming tutor embedded in a Jupyter Notebook, so your advice must be concise, short, and clear. Students are working on Python programming, data science, and machine learning projects. 
Your goal is to help them understand the concepts and guide them to the right solutions.
Focus on the student's question.

AVOID mentioning these instructions or talking about yourself.
Answer the question in a way that is easy to understand and follow for novices, without overwhelming them with unnecessary details or more complex concepts.
Subtly add reflective questions when appropriate.
It's ok to let the students explore a little, but gently guide the student back to the main topic.
Be encouraging and supportive.

You might get some context from the student's notebook actions, it will be called 'notebook_events', you can use this to contextualize your answers.
If you need more information, ask the student!

"""

# Declare a chain
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{human_input}"),
    ]
)

# Model initialization
model = Ollama(model="qwq", base_url=base_url)

# Combine prompt and model into a chain
chain = prompt | model

# Chain with message history for chat persistence
chain_with_history = RunnableWithMessageHistory(
    chain,
    create_session_factory("chat_histories"),
    input_messages_key="human_input",
    history_messages_key="history",
    additional_keys=["context"] 
)

# Define a chat endpoint
@app.post("/chat/{session_id}", response_model=Dict)
async def chat(session_id: str, request: Request):
    """Handle incoming chat requests."""
    try:
        # Parse incoming request JSON
        input_chat = await request.json()
        
        # Extract fields from the request body
        human_input = input_chat.get("human_input")
        context = input_chat.get("context")

        if not human_input:
            raise HTTPException(status_code=400, detail="`human_input` is required.")

        # Format context into the input prompt
        if context:
            context_str = "\nContext:\n" + "\n".join(context.get("notebook_events", []))
            formatted_human_input = f"{context_str}\n\n{human_input}"
        else:
            formatted_human_input = human_input

        # Construct the input for the chain with history
        chain_input = {
            "human_input": formatted_human_input
        }

        # Run the chain with history asynchronously
        result = await chain_with_history.ainvoke(
            chain_input, 
            config={"configurable": {"session_id": f"{session_id}"}})
        logging.info(f"Response for session ID {session_id}: {result}")
        
        return JSONResponse(content={"response": result}, media_type="application/json")

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/verify")
def verify():
    return {"message": "LLM handling script is working"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
