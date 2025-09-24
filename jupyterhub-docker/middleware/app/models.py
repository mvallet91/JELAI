from sqlalchemy import Column, Integer, String, ForeignKey, Table, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship, declarative_base, backref
from datetime import datetime

Base = declarative_base()

# --- Normalized Role & Relationship Models ---
# We introduce explicit tables with integer primary keys to allow future
# metadata (timestamps, status flags) and to align with the technical spec.

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    full_name = Column(String)
    # Retain legacy role column for backward compatibility / existing data.
    # Source of truth for role moving forward is UserRole table.
    role = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user_role = relationship('UserRole', uselist=False, back_populates='user', cascade="all, delete-orphan")
    teaching_assignments = relationship('CourseTeacher', back_populates='teacher', cascade="all, delete-orphan")
    enrollments = relationship('Enrollment', back_populates='student', cascade="all, delete-orphan")

    @property
    def effective_role(self):
        return self.user_role.role if self.user_role else self.role

class UserRole(Base):
    __tablename__ = 'user_roles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), unique=True, nullable=False, index=True)
    role = Column(String, nullable=False)  # CHECK constraint could be added in migrations
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship('User', back_populates='user_role')

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(Text)
    learning_materials_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    teacher_links = relationship('CourseTeacher', back_populates='course', cascade="all, delete-orphan")
    student_links = relationship('Enrollment', back_populates='course', cascade="all, delete-orphan")
    assignments = relationship('Assignment', back_populates='course', cascade="all, delete-orphan")

    @property
    def teachers(self):
        return [ct.teacher for ct in self.teacher_links]

    @property
    def students(self):
        return [en.student for en in self.student_links]

class CourseTeacher(Base):
    __tablename__ = 'course_teachers'
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('course_id', 'teacher_id', name='uq_course_teacher'),)

    course = relationship('Course', back_populates='teacher_links')
    teacher = relationship('User', back_populates='teaching_assignments')

class Enrollment(Base):
    __tablename__ = 'enrollments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (UniqueConstraint('course_id', 'student_id', name='uq_course_student'),)

    course = relationship('Course', back_populates='student_links')
    student = relationship('User', back_populates='enrollments')

class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey('courses.id'), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    due_date = Column(DateTime)
    learning_objectives = Column(Text)  # Could become JSON in future
    created_at = Column(DateTime, default=datetime.utcnow)

    course = relationship('Course', back_populates='assignments')

# NOTE: For migrations we would normally use Alembic; here, create_all will
# attempt to add missing tables. Existing association tables (if any) are
# replaced by normalized tables; manual data migration may be required.
