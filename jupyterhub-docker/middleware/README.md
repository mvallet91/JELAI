# JELAI Middleware

This directory contains the middleware services for the JELAI (Jupyter Environment for Learning AI) project. It acts as the backend processing unit for student interactions within the JupyterLab environment.

## Components

1.  **Tutor Agent (`ta_handler.py`)**:
    *   Receives student messages from the JupyterLab extension (`chat_interact.py`).
    *   Classifies the student message with the categories of `inputs/agent_config.yaml` (by default instrumental, executive, other) using an LLM.
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

*   **LLM connection**: environment variables from `jupyterhub-docker/.env` (`LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_MODEL_<ROLE>`). `llm_client.py` sends all LLM requests to the OpenAI-compatible `/chat/completions` API. See `docs/llm-providers.md` in the repository root.
*   **Tutor behavior**: `inputs/agent_config.yaml` (identification, classification, interventions, proactivity, commands). `config_loader.py` merges it over the copy in the image (`/app/defaults/agent_config.yaml`) and reads it again when it changes. `pedagogy.py` applies the classification and the reactive intervention rules. See `docs/teacher-configuration.md`.
*   **Teacher pages**: `TEACHER_PASSWORD` (and optionally `TEACHER_USERNAME`) enable the dashboard (`/teacher-view`) and the settings page (`/teacher-settings`) with HTTP Basic authentication.
*   **Other**: `EA_URL` (the internal URL of the EA), `DATABASE_FILE`, `ETHERPAD_URL`, `ETHERPAD_API_KEY_FILE`, `ETHERPAD_PAD_ID` (one pad for all students, development only), `TA_WORKERS`, `EA_WORKERS`.

## Activity logs

The notebooks send their processed activity logs with each request (`structured_logs`). The middleware keeps them in `/app/chat_histories/student_logs/<student>.json`, because it cannot read the volumes of the student containers. The learning story and the learner model use these files.

## Database

A SQLite database (`chat_history.db` by default, stored in the `/app/chat_histories` volume) is used to store:

*   `chat_history`: Records of student questions and TA responses, including classification.
*   `student_profiles`: JSON blobs containing aggregated data about each student's interactions (counts, flags, example questions).

## Running

This middleware is designed to be run as a Docker container, typically orchestrated using `docker-compose`. See `docker-compose-dev.yml` for the development setup.

The `start.sh` script is the entry point for the container, responsible for:
1.  Starting Fluentd.
2.  Starting the EA handler using Uvicorn.
3.  Starting the TA handler using Uvicorn.

## API Endpoints

*   `POST /receive_student_message` (TA): Main endpoint for receiving messages from JupyterLab.
*   `POST /expert_query` (EA): Endpoint for the TA to get technical information.
*   `GET /verify_ta` (TA): Health check endpoint.
*   `GET /verify_ea` (EA): Health check endpoint.
*   `GET /health` (TA): Health check with the LLM settings (without the key).
*   `POST /evaluate_proactivity` (TA): Decides about a proactive message.
*   `GET /agent_config` (TA): The student-facing part of the configuration, for the notebooks.
*   `/teacher/...`, `/teacher-view`, `/teacher-settings` (TA): Teacher dashboard and settings (password necessary).