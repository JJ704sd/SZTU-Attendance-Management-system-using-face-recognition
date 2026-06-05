"""
models/course.py — 课程 & 教室 & 实验室
"""
from sqlalchemy import Column, Integer, String, Float, SmallInteger, ForeignKey, Enum

from src.db import Base


class Course(Base):
    __tablename__ = "course"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_code = Column(String(20), unique=True, nullable=False)
    course_name = Column(String(100), nullable=False)
    course_type = Column(
        Enum("theory", "experiment", name="course_type"),
        nullable=False,
        default="theory",
    )
    teacher_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    credit = Column(Float, default=2.0)
    semester = Column(String(20))

    def __repr__(self):
        return f"<Course {self.course_code} {self.course_name}>"


class Classroom(Base):
    __tablename__ = "classroom"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    location = Column(String(100))
    capacity = Column(Integer, default=60)
    has_camera = Column(SmallInteger, default=1)

    def __repr__(self):
        return f"<Classroom {self.name} @ {self.location}>"


class Laboratory(Base):
    __tablename__ = "laboratory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    location = Column(String(100))
    safety_level = Column(SmallInteger, nullable=False, comment="1-5")
    required_training = Column(String(50))
    manager_id = Column(Integer, ForeignKey("user.id"))

    def __repr__(self):
        return f"<Lab {self.name} L{self.safety_level}>"
