#!/bin/bash
#
# test_dev_auth.sh - Exercises common API flows using the dev auth bypass.
#
# This script requires `jq` to parse JSON responses.
# You can install it with: sudo apt-get install jq
#
# Usage:
# 1. Make sure the JELAI services are running (docker compose up).
# 2. Ensure the `ALLOW_DEV_AUTH=1` environment variable is set for the admin-dashboard service.
# 3. Run the script from your shell: bash test_dev_auth.sh

# --- Configuration ---
# Adjust these if your ports or user names are different.
DASHBOARD_URL="http://localhost:8006"
ADMIN_USER="admin"
TEACHER_USER="teacher1"
STUDENT_USER="student1"
COURSE_NAME="Dev Auth Test Course"

# --- Helper Functions ---
info() {
    echo "[INFO] $1"
}

# --- Script ---
info "Starting dev auth test script..."

# 1. Create a new course as the admin user
info "Step 1: Creating a new course ('$COURSE_NAME') as user '$ADMIN_USER'..."
RESPONSE=$(curl -s -X POST "$DASHBOARD_URL/api/proxy/courses" \
  -H "Authorization: Bearer $ADMIN_USER" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"$COURSE_NAME\",\"description\":\"Created by test script\",\"learning_materials_path\":\"test-course\"}")

COURSE_ID=$(echo "$RESPONSE" | jq -r '.id')

if [ -z "$COURSE_ID" ] || [ "$COURSE_ID" == "null" ]; then
    echo "[ERROR] Failed to create course. Response: $RESPONSE"
    exit 1
fi
info "-> Course created successfully with ID: $COURSE_ID"
echo

# 2. Enroll a student into the course as a teacher
info "Step 2: Enrolling student '$STUDENT_USER' into course $COURSE_ID as user '$TEACHER_USER'..."
ENROLL_RESPONSE=$(curl -s -X POST "$DASHBOARD_URL/api/proxy/courses/$COURSE_ID/students" \
  -H "Authorization: Bearer $TEACHER_USER" \
  -H "Content-Type: application/json" \
  -d "{\"usernames\": [\"$STUDENT_USER\"]}")

# Check if enrollment was successful (adjust check based on actual API response)
if [[ ! $(echo "$ENROLL_RESPONSE" | jq -r '.message') == *"successfully enrolled"* ]]; then
    echo "[ERROR] Failed to enroll student. Response: $ENROLL_RESPONSE"
    exit 1
fi
info "-> Student enrolled successfully."
echo

# 3. Verify the student is in the course list
info "Step 3: Verifying enrollment by listing students in course $COURSE_ID as user '$TEACHER_USER'..."
STUDENTS_LIST=$(curl -s "$DASHBOARD_URL/api/proxy/courses/$COURSE_ID/students" \
  -H "Authorization: Bearer $TEACHER_USER")

STUDENT_FOUND=$(echo "$STUDENTS_LIST" | jq -r ".[] | select(.username==\"$STUDENT_USER\") | .username")

if [ "$STUDENT_FOUND" == "$STUDENT_USER" ]; then
    info "-> SUCCESS: Student '$STUDENT_USER' found in course enrollment list."
else
    echo "[ERROR] FAILED: Student '$STUDENT_USER' not found in course enrollment list."
    echo "Current student list: $STUDENTS_LIST"
    exit 1
fi
echo

info "All tests passed!"
