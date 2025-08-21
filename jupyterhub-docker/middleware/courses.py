import os
import json
from typing import Dict, List, Optional
from uuid import uuid4

DATA_DIR = os.environ.get('COURSES_DATA_DIR', '/app/data')
COURSES_FILE = os.path.join(DATA_DIR, 'courses.json')

def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def load_courses() -> Dict[str, dict]:
    ensure_data_dir()
    if not os.path.exists(COURSES_FILE):
        return {}
    with open(COURSES_FILE, 'r') as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def save_courses(courses: Dict[str, dict]):
    ensure_data_dir()
    with open(COURSES_FILE, 'w') as f:
        json.dump(courses, f, indent=2)

def list_courses() -> List[dict]:
    return list(load_courses().values())

def get_course(course_id: str) -> Optional[dict]:
    return load_courses().get(course_id)

def create_course(title: str, description: str = "", materials: Optional[List[str]] = None) -> dict:
    courses = load_courses()
    course_id = str(uuid4())
    course = {
        'id': course_id,
        'title': title,
        'description': description,
        'materials': materials or [],
        'teachers': [],
        'students': []
    }
    courses[course_id] = course
    save_courses(courses)
    return course

def assign_teacher(course_id: str, teacher_username: str) -> dict:
    courses = load_courses()
    if course_id not in courses:
        raise KeyError('course not found')
    if teacher_username not in courses[course_id]['teachers']:
        courses[course_id]['teachers'].append(teacher_username)
        save_courses(courses)
    return courses[course_id]

def enroll_student(course_id: str, student_username: str) -> dict:
    courses = load_courses()
    if course_id not in courses:
        raise KeyError('course not found')
    if student_username not in courses[course_id]['students']:
        courses[course_id]['students'].append(student_username)
        save_courses(courses)
    return courses[course_id]

def unenroll_student(course_id: str, student_username: str) -> dict:
    courses = load_courses()
    if course_id not in courses:
        raise KeyError('course not found')
    if student_username in courses[course_id]['students']:
        courses[course_id]['students'].remove(student_username)
        save_courses(courses)
    return courses[course_id]
