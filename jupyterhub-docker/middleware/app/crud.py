from sqlalchemy.orm import Session
from . import models, schemas
from typing import List, Optional

def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.username == username).first()

def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    db_user = models.User(**user.dict())
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_course(db: Session, course_id: int) -> Optional[models.Course]:
    return db.query(models.Course).filter(models.Course.id == course_id).first()

def get_courses(db: Session) -> List[models.Course]:
    return db.query(models.Course).all()

def create_course(db: Session, course: schemas.CourseCreate) -> models.Course:
    db_course = models.Course(**course.dict())
    db.add(db_course)
    db.commit()
    db.refresh(db_course)
    return db_course

def assign_teacher_to_course(db: Session, course: models.Course, teacher: models.User):
    if teacher not in course.teachers:
        course.teachers.append(teacher)
        db.commit()
        db.refresh(course)
    return course

def enroll_student_in_course(db: Session, course: models.Course, student: models.User):
    if student not in course.students:
        course.students.append(student)
        db.commit()
        db.refresh(course)
    return course

def unenroll_student_from_course(db: Session, course: models.Course, student: models.User):
    if student in course.students:
        course.students.remove(student)
        db.commit()
        db.refresh(course)
    return course
