#!/usr/bin/env python3
"""Seed initial courses using learning materials present in the mounted volumes."""
import os
from pathlib import Path
from courses import create_course, assign_teacher

MATERIALS_DIR = '/app/learning_materials'
INPUTS_DIR = '/app/inputs'

def find_material_files():
    files = []
    if os.path.exists(MATERIALS_DIR):
        for p in Path(MATERIALS_DIR).rglob('*'):
            if p.is_file():
                files.append(str(p.relative_to(MATERIALS_DIR)))
    return files


def seed():
    # Create DataScience101 if not exists
    existing = [c for c in create_course.__module__ and []]
    # We'll attempt to create unconditionally but guard by title
    materials = find_material_files()
    title = 'DataScience101'
    description = 'Introductory Data Science course using provided learning materials.'

    # Simple check: if a course with same title exists, skip
    from courses import load_courses
    courses = load_courses()
    for c in courses.values():
        if c.get('title') == title:
            print('Course DataScience101 already exists. Skipping seed.')
            return

    course = create_course(title=title, description=description, materials=materials)
    print(f"Created course: {course['id']} - {course['title']}")

    # Optionally assign a default teacher from env
    default_teacher = os.environ.get('DEFAULT_TEACHER', 'teacher1')
    assign_teacher(course['id'], default_teacher)
    print(f"Assigned teacher '{default_teacher}' to course {course['id']}")

if __name__ == '__main__':
    seed()
