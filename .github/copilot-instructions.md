# Copilot Instructions for JELAI

## System Overview
- JELAI is a multi-container, JupyterHub-based platform for learning analytics and AI education.
- Major components:
  - **JupyterHub**: Handles authentication (nativeauthenticator) and spawns per-user JupyterLab servers.
  - **User Notebook**: Each user gets a container with JupyterLab, chat integration, and telemetry logging (see `jupyterhub-docker/user-notebook/`).
  - **Middleware**: Backend services (Tutor Agent, Expert Agent, Admin API) for chat, analytics, and admin operations (see `jupyterhub-docker/middleware/`).
  - **Admin Dashboard**: FastAPI app for educators to manage courses, enrollments, and analytics (see `jupyterhub-docker/admin-dashboard/`).
  - **Ollama**: LLM server, can be local or remote.

## Data Flows & Integration
- Student chat and telemetry logs are processed in the user notebook, sent to middleware for analysis and storage.
- Middleware uses SQLite (`chat_history.db`) for chat and profile data; Admin Dashboard uses its own SQLite DB for courses/enrollments.
- Admin Dashboard communicates with Middleware via REST API (see `/api/proxy/`).
- Learning materials are shared via Docker volumes (`learning_materials/`), copied into user workspaces at spawn.

## Developer Workflows
- **Development**: Use `docker-compose.yml` to spin up all services.
- **Admin Dashboard**: Accessible via JupyterHub admin panel or directly on port 8006 in dev.
- **Testing**: No global test runner; test individual scripts or endpoints as needed. Rebuild and restart containers as necessary.
- **Logs**: Collected via Fluentd, stored in middleware volumes. Also each container has specific logs, see the start.sh in middleware and Dockerfile in user-notebook. Specifically for services inside middleware:
  - For the ea handler: /var/log/llm-handler/ea-logs.txt
  - For the ta handler: /var/log/llm-handler/ta-logs.txt
  - For the admin API: /var/log/llm-handler/admin-logs.txt

## Project Conventions
- All persistent data (notebooks, logs, chat histories) is stored in Docker volumes.
- Use environment variables for service URLs, secrets, and configuration (see `.env.example` files).
- FastAPI is used for all web APIs; prefer async endpoints.
- Templates and static assets for the admin dashboard are in `jupyterhub-docker/admin-dashboard/templates/` and `static/`.
- Learning materials for courses are in `user-notebook/learning_materials/` and referenced by course logic.

## Patterns & Examples
- To add a new admin dashboard feature, update both FastAPI endpoints and Jinja2 templates.
- For new analytics, extend middleware's `ta-handler.py` or `ea-handler.py` and update the database schema if needed.
- To add a new course, update the admin dashboard DB and learning materials volume.

## Key Files & Directories
- `docker-compose.yml`: Main entry for environment.
- `jupyterhub-docker/admin-dashboard/app.py`: Admin dashboard FastAPI app.
- `jupyterhub-docker/middleware/ta-handler.py`, `ea-handler.py`: Core backend logic.
- `jupyterhub-docker/middleware/admin-api.py`: Admin API for managing the dashboard system.
- `jupyterhub-docker/user-notebook/`: User JupyterLab image and scripts.
- `analysis/`: Research and analytics scripts/notebooks.

---
For more, see the main `README.md` and service-specific READMEs.
