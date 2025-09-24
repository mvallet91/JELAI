from app import models, database
from sqlalchemy.orm import Session

SEED_USERS = [
    {"username": "admin", "full_name": "System Admin", "role": "admin"},
    {"username": "teacher1", "full_name": "Teacher One", "role": "teacher"},
    {"username": "teacher2", "full_name": "Teacher Two", "role": "teacher"},
    {"username": "student1", "full_name": "Student One", "role": "student"},
    {"username": "student2", "full_name": "Student Two", "role": "student"},
]

SEED_COURSES = [
    {"name": "Intro Data Science", "description": "Basics of DS", "learning_materials_path": "intro-ds"},
    {"name": "Advanced ML", "description": "Deep dive into ML", "learning_materials_path": "adv-ml"},
]

COURSE_ASSIGNMENTS = {
    # course_name: [teacher_usernames]
    "Intro Data Science": ["teacher1"],
    "Advanced ML": ["teacher2"],
}

COURSE_ENROLLMENTS = {
    "Intro Data Science": ["student1", "student2"],
    "Advanced ML": ["student1"],
}

def get_or_create_user(db: Session, username: str, full_name: str):
    user = db.query(models.User).filter_by(username=username).first()
    if not user:
        user = models.User(username=username, full_name=full_name)
        db.add(user)
        db.flush()
    return user

def get_or_create_role(db: Session, user: models.User, role: str):
    if user.user_role:
        # Update if different
        if user.user_role.role != role:
            user.user_role.role = role
    else:
        db.add(models.UserRole(user_id=user.id, role=role))

def get_or_create_course(db: Session, name: str, description: str, learning_materials_path: str):
    course = db.query(models.Course).filter_by(name=name).first()
    if not course:
        course = models.Course(name=name, description=description, learning_materials_path=learning_materials_path)
        db.add(course)
        db.flush()
    return course

def ensure_teacher(db: Session, course: models.Course, teacher: models.User):
    exists = any(link.teacher_id == teacher.id for link in course.teacher_links)
    if not exists:
        db.add(models.CourseTeacher(course_id=course.id, teacher_id=teacher.id))

def ensure_enrollment(db: Session, course: models.Course, student: models.User):
    exists = any(link.student_id == student.id for link in course.student_links)
    if not exists:
        db.add(models.Enrollment(course_id=course.id, student_id=student.id))

def init_db():
    models.Base.metadata.create_all(bind=database.engine)
    db = database.SessionLocal()
    try:
        # Seed users & roles
        for u in SEED_USERS:
            user = get_or_create_user(db, u['username'], u['full_name'])
            get_or_create_role(db, user, u['role'])
        db.commit()

        # Seed courses
        name_to_course = {}
        for cdef in SEED_COURSES:
            course = get_or_create_course(db, cdef['name'], cdef['description'], cdef['learning_materials_path'])
            name_to_course[cdef['name']] = course
        db.commit()

        # Assign teachers
        for cname, teacher_usernames in COURSE_ASSIGNMENTS.items():
            course = name_to_course.get(cname)
            if not course:
                continue
            for tuser in teacher_usernames:
                teacher = db.query(models.User).filter_by(username=tuser).first()
                if teacher:
                    ensure_teacher(db, course, teacher)
        db.commit()

        # Enroll students
        for cname, student_usernames in COURSE_ENROLLMENTS.items():
            course = name_to_course.get(cname)
            if not course:
                continue
            for suser in student_usernames:
                student = db.query(models.User).filter_by(username=suser).first()
                if student:
                    ensure_enrollment(db, course, student)
        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
