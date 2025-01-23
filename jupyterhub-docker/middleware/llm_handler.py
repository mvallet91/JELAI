#!/usr/bin/env python
"""Example of a chat server with persistence handled on the backend."""

import re
import os
import logging
import json
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

##################################################
# Constants for group assignment and storage
GROUP_A = "group_a"
GROUP_B = "group_b"
GROUP_ASSIGNMENTS_FILE = "group_assignments.json"

# Load or initialize group assignments
def load_group_assignments():
    try:
        with open(GROUP_ASSIGNMENTS_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_group_assignments(assignments):
    with open(GROUP_ASSIGNMENTS_FILE, "w") as f:
        json.dump(assignments, f, indent=4)

group_assignments = load_group_assignments()
##################################################

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
You are Juno, an experienced data science and programming tutor embedded in a JupyterLab interface, so your responses must be concise. 
Students are working on a data science task using Python with pandas, matplotlib, and similar libraries to analyse a dataset of shark observations. 
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

Together with the <User Message> from the student, you might get some <Relevant Context> from the student's notebook actions, you can use this to contextualize your answers.
If you need more information, ask the student!

"""

system_prompt_basic = """
You are Juno, a helpful AI assistant embedded in a JupyterLab interface, so your responses must be concise.

Together with the <User Message>, you might get some <Relevant Context> from the user's notebook actions, you can use this to contextualize your answers.
"""

# Model initialization
model = Ollama(model="gemma2:27b", base_url=base_url)

# Define a chat endpoint
@app.post("/chat/{session_id}", response_model=Dict)
async def chat(session_id: str, request: Request):
    """Handle incoming chat requests."""
    try:

        ##################################################
        # if session_id not in group_assignments:
        #     if len(group_assignments) % 2 == 0:  # Simple alternating assignment
        #         group_assignments[session_id] = GROUP_A
        #     else:
        #         group_assignments[session_id] = GROUP_B
        #     save_group_assignments(group_assignments)
        #     logging.info(f"Assigned session {session_id} to {group_assignments[session_id]}")

        # # Select the correct system prompt based on group
        # if group_assignments[session_id] == GROUP_A:
        #     system_prompt_to_use = system_prompt
        # elif group_assignments[session_id] == GROUP_B:
        #     system_prompt_to_use = system_prompt_basic
        # else:
        #     raise ValueError(f"Invalid group assignment for session {session_id}")
        
        # Extract sender from session_id
        try:
            sanitized_sender = session_id.split("_")[0] # Extract the first part of the session id
        except IndexError:
            raise HTTPException(status_code=400, detail="Invalid session_id format. Expected sender_filename")
        
        # Assign group based on sender, not full session_id
        group_assignments = load_group_assignments() 
        if sanitized_sender not in group_assignments:
            if len(group_assignments) % 2 == 0:
                group_assignments[sanitized_sender] = GROUP_A
            else:
                group_assignments[sanitized_sender] = GROUP_B
            save_group_assignments(group_assignments)
            logging.info(f"Assigned sender {sanitized_sender} to {group_assignments[sanitized_sender]}")
        
        # Select prompt based on sender's group
        if group_assignments[sanitized_sender] == GROUP_A:
            system_prompt_to_use = system_prompt
        elif group_assignments[sanitized_sender] == GROUP_B:
            system_prompt_to_use = system_prompt_basic
        else:
            raise ValueError(f"Invalid group assignment for sender {sanitized_sender}")
        ##################################################


        # Declare a chain
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt_to_use),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{human_input}"),
            ]
        )

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
        ##################################################

        # Parse incoming request JSON
        input_chat = await request.json()
        
        # Extract fields from the request body
        human_input = input_chat.get("human_input")
        context = input_chat.get("context")

        if not human_input:
            raise HTTPException(status_code=400, detail="`human_input` is required.")

        # Format context into the input prompt
        if context:
            context_str = "\n".join(context.get("notebook_events", []))
            formatted_human_input = rf"<User message>{human_input}<\User message>\n\n<Relevant context>{context_str}<\Relevant context>\n\n"
        else:
            formatted_human_input = human_input

        # Construct the input for the chain with history
        chain_input = {
            "human_input": formatted_human_input
        }
        logging.info(f"Request for session ID {session_id}: {chain_input}")

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

# Add an endpoint to retrieve group assignments (for analysis)
@app.get("/group_assignments")
async def get_group_assignments():
    return group_assignments

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
