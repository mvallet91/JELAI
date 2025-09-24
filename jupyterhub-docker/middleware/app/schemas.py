from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    full_name: Optional[str] = None
    role: str

class UserCreate(UserBase):
    pass

class User(UserBase):
    id: int
    created_at: datetime
    class Config:
        orm_mode = True

class CourseBase(BaseModel):
    name: str
    description: Optional[str] = None
    learning_materials_path: Optional[str] = None

class CourseCreate(CourseBase):
    pass

class Course(CourseBase):
    id: int
    created_at: datetime
    teachers: List[User] = []
    students: List[User] = []
    class Config:
        orm_mode = True

class AssignmentBase(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None
    learning_objectives: Optional[str] = None

class AssignmentCreate(AssignmentBase):
    pass

class Assignment(AssignmentBase):
    id: int
    course_id: int
    created_at: datetime
    class Config:
        orm_mode = True
