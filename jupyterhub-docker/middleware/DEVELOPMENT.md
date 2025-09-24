# Middleware Development Guide

## 1. Overview
This document outlines the development workflow for the JELAI middleware service. The middleware is a FastAPI application that serves as the backend for the JELAI platform. It is responsible for handling course management, user roles, enrollments, and analytics data, as defined in the multi-course technical specification.

## 2. Project Structure
To support the new features, the middleware will be organized as a Python package. Key files and directories include:
- `app/`: The main application source directory.
  - `__init__.py`: Makes the `app` directory a package.
  - `main.py`: The main FastAPI application entry point (renamed from `admin_api.py`).
  - `database.py`: Handles database connection, session management, and engine creation.
  - `models.py`: Contains all SQLAlchemy ORM models (e.g., `Course`, `User`, `UserRole`, `Enrollment`).
  - `schemas.py`: Contains all Pydantic schemas for API request/response validation.
  - `crud.py`: Contains functions for all database CRUD (Create, Read, Update, Delete) operations.
  - `api/`: Directory for API route modules.
- `scripts/`:
  - `initialize_db.py`: A script to create the database schema and seed it with initial test data.
- `tests/`:
  - Contains all `pytest` tests. Tests should be organized to mirror the application structure.
- `pyproject.toml` & `setup.cfg`: Packaging and project configuration files.

## 3. Setting Up the Development Environment

### Prerequisites
- Docker and Docker Compose must be installed.

### Initial Setup
1.  **Start the service:** From the `jupyterhub-docker` directory, run:
    ```bash
    docker compose up -d --build middleware
    ```
    This will build the middleware image and start the container. The `chat_history.db` SQLite file will be created and persisted in the `jupyterhub-docker/middleware/` directory on the host.

2.  **Initialize the Database:** The new tables required for the multi-course feature must be created and seeded.
    Run the initialization script inside the running container:
    ```bash
    # Get the container ID
    CONTAINER_ID=$(docker compose ps -q middleware)
    # Execute the script
    docker exec $CONTAINER_ID python /app/scripts/initialize_db.py
    ```
    This script will create the `courses`, `user_roles`, `enrollments`, and `course_teachers` tables. You can modify this script to add or change the default seed data (e.g., test users, courses, and teachers) for your development needs.

## 4. Development Workflow

### Fast Iteration (In-Place Editing)
For rapid development, you can copy files into the running container and reinstall the package in editable mode. This avoids a full image rebuild for every change.

1.  **Copy updated files into the container:**
    From the repository root (`JELAI/`), run the following commands.
    ```bash
    CONTAINER_ID=$(docker-compose -f jupyterhub-docker/docker-compose.yml ps -q middleware)
    # Copy the entire app directory
    docker cp jupyterhub-docker/middleware/app/. $CONTAINER_ID:/app/app
    # Copy tests
    docker cp jupyterhub-docker/tests/. $CONTAINER_ID:/app/tests
    # Copy other files if they change
    docker cp jupyterhub-docker/middleware/scripts/initialize_db.py $CONTAINER_ID:/app/scripts/initialize_db.py
    ```

2.  **Install and run tests inside the container:**
    The middleware service runs as the `appuser`. For package management tasks, you need to execute commands as `root`.
    ```bash
    # Install the package in editable mode
    docker exec -u root $CONTAINER_ID pip install -e /app
    # Run tests to validate your changes
    docker exec -u root $CONTAINER_ID pytest -q /app/tests
    ```
    *Note: The service will automatically reload when it detects source code changes.*

### Making Changes Persistent (Rebuilding the Image)
Once your changes are complete and tested, you must rebuild the Docker image to make them permanent.

1.  **Ensure all new and modified files are committed to the repository.** This includes new source files (`database.py`, `models.py`, etc.) and any changes to the `Dockerfile`.

2.  **Rebuild and restart the service:**
    From the `jupyterhub-docker` directory:
    ```bash
    # Rebuild the middleware image
    docker compose build middleware
    # Restart the service to apply changes
    docker compose up -d middleware
    ```

## 5. Testing
The testing strategy relies on `pytest` and a seeded database.

- **Test Database:** Tests will run against the same `chat_history.db` file used for development. The `initialize_db.py` script is the source of truth for the test data.
- **Running Tests:** As shown above, tests can be executed directly inside the container. For more detailed output, remove the `-q` flag:
  ```bash
  docker exec -u root $(docker compose ps -q middleware) pytest /app/tests
  ```
- **Writing Tests:** When adding new features, create corresponding tests. Use the seeded data to test API endpoints for different user roles (`student`, `teacher`, `admin`) and ensure course isolation is enforced correctly.

