




from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, schemas, crud, database
from typing import List

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="JELAI Middleware API", version="1.0.0")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# User endpoints
@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_username(db, username=user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return crud.create_user(db, user)

@app.get("/users/", response_model=List[schemas.User])
def list_users(db: Session = Depends(get_db)):
    return db.query(models.User).all()

# List users by role (for admin dashboard assignment)
@app.get("/users/role/{role}", response_model=List[schemas.User])
def list_users_by_role(role: str, db: Session = Depends(get_db)):
    return db.query(models.User).filter(models.User.role == role).all()

# Course endpoints
@app.post("/courses/", response_model=schemas.Course)
def create_course(course: schemas.CourseCreate, db: Session = Depends(get_db)):
    return crud.create_course(db, course)

@app.get("/courses/", response_model=List[schemas.Course])
def list_courses(db: Session = Depends(get_db)):
    return crud.get_courses(db)

# Assign teacher to course
@app.post("/courses/{course_id}/teachers/{teacher_id}")
def assign_teacher(course_id: int, teacher_id: int, db: Session = Depends(get_db)):
    course = crud.get_course(db, course_id)
    teacher = db.query(models.User).filter(models.User.id == teacher_id, models.User.role == 'teacher').first()
    if not course or not teacher:
        raise HTTPException(status_code=404, detail="Course or teacher not found")
    return crud.assign_teacher_to_course(db, course, teacher)

# Remove teacher from course
@app.delete("/courses/{course_id}/teachers/{teacher_id}")
def remove_teacher(course_id: int, teacher_id: int, db: Session = Depends(get_db)):
    course = crud.get_course(db, course_id)
    teacher = db.query(models.User).filter(models.User.id == teacher_id, models.User.role == 'teacher').first()
    if not course or not teacher:
        raise HTTPException(status_code=404, detail="Course or teacher not found")
    if teacher in course.teachers:
        course.teachers.remove(teacher)
        db.commit()
        db.refresh(course)
    return course

# Enroll student in course
@app.post("/courses/{course_id}/students/{student_id}")
def enroll_student(course_id: int, student_id: int, db: Session = Depends(get_db)):
    course = crud.get_course(db, course_id)
    student = db.query(models.User).filter(models.User.id == student_id, models.User.role == 'student').first()
    if not course or not student:
        raise HTTPException(status_code=404, detail="Course or student not found")
    return crud.enroll_student_in_course(db, course, student)

# Unenroll student from course
@app.delete("/courses/{course_id}/students/{student_id}")
def unenroll_student(course_id: int, student_id: int, db: Session = Depends(get_db)):
    course = crud.get_course(db, course_id)
    student = db.query(models.User).filter(models.User.id == student_id, models.User.role == 'student').first()
    if not course or not student:
        raise HTTPException(status_code=404, detail="Course or student not found")
    return crud.unenroll_student_from_course(db, course, student)
