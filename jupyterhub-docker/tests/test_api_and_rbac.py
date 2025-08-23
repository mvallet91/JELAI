import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import os
import sys

# Add middleware directory to path to import app
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'middleware'))
from admin_api import app, get_user_from_request

client = TestClient(app)

# Mock course data
mock_courses = {
    "course-1": {"id": "course-1", "title": "Course 1", "teachers": ["teacher-1"], "students": ["student-1"]},
    "course-2": {"id": "course-2", "title": "Course 2", "teachers": ["teacher-2"], "students": ["student-2"]},
}

def mock_get_course(course_id):
    return mock_courses.get(course_id)

def mock_list_courses():
    return list(mock_courses.values())

@pytest.fixture(autouse=True)
def patch_course_functions():
    with patch('admin_api.get_course', side_effect=mock_get_course) as mock_get:
        with patch('admin_api.list_courses', side_effect=mock_list_courses) as mock_list:
            yield mock_get, mock_list

def override_get_user_from_request(request):
    return request.headers.get("X-Test-User", "anonymous")

app.dependency_overrides[get_user_from_request] = override_get_user_from_request

# --- Test Cases ---

def test_list_courses_as_admin():
    response = client.get("/api/courses", headers={"X-Test-User": "admin"})
    assert response.status_code == 200
    assert len(response.json()) == 2

def test_list_courses_as_teacher():
    response = client.get("/api/courses", headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 1
    assert courses[0]['id'] == 'course-1'

def test_list_courses_as_student():
    response = client.get("/api/courses", headers={"X-Test-User": "student-1"})
    assert response.status_code == 200
    courses = response.json()
    assert len(courses) == 1
    assert courses[0]['id'] == 'course-1'

def test_list_courses_as_unauthorized_user():
    response = client.get("/api/courses", headers={"X-Test-User": "other-user"})
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_get_course_as_admin():
    response = client.get("/api/courses/course-1", headers={"X-Test-User": "admin"})
    assert response.status_code == 200
    assert response.json()['id'] == 'course-1'

def test_get_course_as_teacher():
    response = client.get("/api/courses/course-1", headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 200
    assert response.json()['id'] == 'course-1'

def test_get_course_as_enrolled_student():
    response = client.get("/api/courses/course-1", headers={"X-Test-User": "student-1"})
    assert response.status_code == 200
    assert response.json()['id'] == 'course-1'

def test_get_course_as_other_teacher_fail():
    response = client.get("/api/courses/course-1", headers={"X-Test-User": "teacher-2"})
    assert response.status_code == 403

def test_get_course_as_other_student_fail():
    response = client.get("/api/courses/course-1", headers={"X-Test-User": "student-2"})
    assert response.status_code == 403

@patch('admin_api.enroll_student')
def test_enroll_student_as_teacher(mock_enroll):
    mock_enroll.return_value = {"status": "ok"}
    response = client.post("/api/courses/course-1/enroll", data={"student": "new-student"}, headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 200
    mock_enroll.assert_called_with("course-1", "new-student")

@patch('admin_api.enroll_student')
def test_enroll_student_as_other_teacher_fail(mock_enroll):
    response = client.post("/api/courses/course-1/enroll", data={"student": "new-student"}, headers={"X-Test-User": "teacher-2"})
    assert response.status_code == 403
    mock_enroll.assert_not_called()

@patch('admin_api.unenroll_student')
def test_unenroll_student_as_teacher(mock_unenroll):
    mock_unenroll.return_value = {"status": "ok"}
    response = client.post("/api/courses/course-1/unenroll", data={"student": "student-1"}, headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 200
    mock_unenroll.assert_called_with("course-1", "student-1")

@patch('admin_api.unenroll_student')
def test_unenroll_student_as_other_teacher_fail(mock_unenroll):
    response = client.post("/api/courses/course-1/unenroll", data={"student": "student-1"}, headers={"X-Test-User": "teacher-2"})
    assert response.status_code == 403
    mock_unenroll.assert_not_called()

@patch('admin_api.assign_teacher')
def test_assign_teacher_as_admin(mock_assign):
    mock_assign.return_value = {"status": "ok"}
    response = client.post("/api/courses/course-1/assign-teacher", data={"teacher": "new-teacher"}, headers={"X-Test-User": "admin"})
    assert response.status_code == 200
    mock_assign.assert_called_with("course-1", "new-teacher")

@patch('admin_api.assign_teacher')
def test_assign_teacher_as_teacher_fail(mock_assign):
    response = client.post("/api/courses/course-1/assign-teacher", data={"teacher": "new-teacher"}, headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 403
    mock_assign.assert_not_called()

@patch('admin_api.create_course')
def test_create_course_as_admin(mock_create):
    mock_create.return_value = {"id": "new-course", "title": "New Course"}
    response = client.post("/api/courses", json={"title": "New Course"}, headers={"X-Test-User": "admin"})
    assert response.status_code == 200
    mock_create.assert_called_with(title="New Course", description=None)

@patch('admin_api.create_course')
def test_create_course_as_teacher_fail(mock_create):
    response = client.post("/api/courses", json={"title": "New Course"}, headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 403
    mock_create.assert_not_called()

@patch('sqlite3.connect')
def test_get_course_analytics_as_teacher(mock_sql_connect):
    # Mock the database connection and cursor
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_sql_connect.return_value = mock_conn
    mock_conn.execute.return_value = mock_cursor
    mock_cursor.fetchall.return_value = [("student-1", 10, "2025-01-01", "2025-01-02")]

    response = client.get("/api/courses/course-1/analytics", headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 200
    
    # Check that the query was called with the correct student
    mock_conn.execute.assert_called_once()
    args, _ = mock_conn.execute.call_args
    assert "WHERE student_id IN (?)" in args[0]
    assert args[1] == ['student-1']

def test_get_course_analytics_as_other_teacher_fail():
    response = client.get("/api/courses/course-2/analytics", headers={"X-Test-User": "teacher-1"})
    assert response.status_code == 403
