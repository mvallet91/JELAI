# JELAI Middleware

This directory contains the middleware services for the JELAI (Jupyter Environment for Learning AI) project. It acts as the backend processing unit for student interactions within the JupyterLab environment.

## Components

1.  **Tutor Agent (`ta_handler.py`)**:
    *   Receives student messages from the JupyterLab extension (`chat_interact.py`).
    *   Classifies the student's help-seeking type (instrumental, executive, other) using an LLM.
    *   Selects a relevant Learning Objective (LO).
    *   Stores the interaction in the chat history database.
    *   Retrieves the student's profile (interaction history, flags) from the database.
    *   Constructs a prompt for the Expert Agent (EA).
    *   Calls the EA to get concise technical information.
    *   Uses the student's message, profile hints, classification, LO, and EA response to formulate a final pedagogical response using another LLM call.
    *   Stores the final response in the history.
    *   Schedules a background task to update the student's profile.
    *   Returns the final response to the JupyterLab extension.
    *   Runs on port `8004`.

2.  **Expert Agent (`ea_handler.py`)**:
    *   Receives a structured prompt from the TA containing the student's question, LO, assignment context, etc.
    *   Calls an LLM (configured via environment variables) with a specific system prompt instructing it to act as a factual expert, providing concise technical answers without tutoring.
    *   Returns the raw technical information to the TA.
    *   Runs on port `8003`.

3.  **Fluentd (`td-agent.conf`)**:
    *   Collects logs from the TA and EA handlers (and potentially other components).
    *   Configured to forward logs (details depend on `td-agent.conf`). Standard output/error from handlers is also redirected to files in `/var/log/llm-handler/` within the container.

4.  **Utilities (`utils.py`)**: (If applicable) Contains shared functions used by the handlers.

## Configuration

Configuration is primarily handled via environment variables, mainly loaded from a `.env` file using `python-dotenv`. Key variables include:

*   `OLLAMA_BASE_URL`: URL for the Ollama API endpoint (e.g., `http://host.docker.internal:11434`).
*   `WEBUI_API_BASE`: URL for a WebUI API endpoint (optional alternative).
*   `WEBUI_API_KEY`: API key if using WebUI.
*   `OLLAMA_MODEL`/`OLLAMA_CLASSIFICATION_MODEL`/`OLLAMA_RESPONSE_MODEL`/`OLLAMA_EA_MODEL`: Names of the specific Ollama models to use for different tasks.
*   `EA_URL`: The internal URL the TA uses to reach the EA (e.g., `http://localhost:8003` when running in the same container).

## Database

A SQLite database (`chat_history.db` by default, stored in the `/app/chat_histories` volume) is used to store:

*   `chat_history`: Records of student questions and TA responses, including classification.
*   `student_profiles`: JSON blobs containing aggregated data about each student's interactions (counts, flags, example questions).

## Running

This middleware is designed to be run as a Docker container, typically orchestrated using `docker-compose`. See `docker-compose-dev.yml` for the development setup.

The `start.sh` script is the entry point for the container, responsible for:
1.  Activating the Python virtual environment (`/app/.venv`).
2.  Starting Fluentd.
3.  Starting the EA handler using Uvicorn.
4.  Starting the TA handler using Uvicorn.

## API Endpoints

*   `POST /receive_student_message` (TA): Main endpoint for receiving messages from JupyterLab.
*   `POST /expert_query` (EA): Endpoint for the TA to get technical information.
*   `GET /verify_ta` (TA): Health check endpoint.
*   `GET /verify_ea` (EA): Health check endpoint.