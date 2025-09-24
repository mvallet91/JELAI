# Development Authentication Guide

## 1. Overview
This document explains the development-only authentication bypass mechanism for the `admin-dashboard` and `middleware` services. This feature, controlled by the `ALLOW_DEV_AUTH` environment variable, is designed to simplify testing by allowing developers to make authenticated API calls without needing a valid JupyterHub session cookie.

## 2. How It Works
When `ALLOW_DEV_AUTH` is set to a truthy value (`1`, `true`, `yes`), the authentication system is modified:
- **Admin Dashboard**: The dashboard's security dependency is replaced with a mock that extracts user identity from headers or query parameters.
- **Middleware**: The middleware's existing simple auth is used, which already supports this flow.

This allows you to simulate requests as any user (`student`, `teacher`, or `admin`) directly from tools like `curl` or in automated test scripts.

### Supported Authentication Methods
When the bypass is active, you can authenticate by providing a username in one of the following ways:
- **HTTP Header (Bearer Token)**: `Authorization: Bearer <username>`
- **HTTP Header (Custom)**: `X-DEV-USER: <username>`
- **Query Parameter**: `?user=<username>`

### Simulating an Admin User
To perform actions as a system administrator, use the username defined in the `ADMIN_USER` environment variable (default is `admin`).

## 3. Security Warning
**This feature is for development and testing purposes ONLY.** It completely bypasses the standard OAuth2/JupyterHub authentication flow. **Never enable `ALLOW_DEV_AUTH` in a production environment**, as it would expose the system to unauthorized access.

## 4. Usage Examples
The following examples assume the services are running locally, with the admin dashboard on port `8006`.

### Example 1: List All Courses as an Admin
```bash
curl -v 'http://localhost:8006/api/proxy/courses' \
  -H 'Authorization: Bearer admin'
```

### Example 2: Create a New Course as an Admin
```bash
curl -v -X POST 'http://localhost:8006/api/proxy/courses' \
  -H 'Authorization: Bearer admin' \
  -H 'Content-Type: application/json' \
  -d '{"name":"My New Course","description":"A course created via dev auth.","learning_materials_path":"new-course"}'
```

### Example 3: Enroll Students as a Teacher
Assuming a course with ID `1` exists and is managed by `teacher1`:
```bash
curl -v -X POST 'http://localhost:8006/api/proxy/courses/1/students' \
  -H 'Authorization: Bearer teacher1' \
  -H 'Content-Type: application/json' \
  -d '{"usernames": ["student1", "student2"]}'
```

## 5. Automated Test Script
To make testing even easier, a shell script `test_dev_auth.sh` is provided in this directory. It automates a common workflow: creating a course, enrolling a student, and verifying the enrollment.

### Prerequisites
- **`jq`**: The script uses `jq` to parse JSON responses. Install it with `sudo apt-get install jq` (on Debian/Ubuntu).

### How to Run
1.  Ensure the JELAI services are running via `docker compose up`.
2.  Confirm that `ALLOW_DEV_AUTH=1` is set in your `docker-compose.yml` for the `admin-dashboard` service.
3.  Execute the script from the `jupyterhub-docker/admin-dashboard` directory:
    ```bash
    bash test_dev_auth.sh
    ```
The script will print its progress and report success or failure. You can modify the user and course names at the top of the script for different test scenarios.
