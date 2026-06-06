"""
models/course_enrollment.py — 选课表（学生 ↔ 课程 多对多）

Phase 1 / W4：
- 修 attendance_service.close_task_and_mark_absent 用本表代替"role='student' 全部"
- 业务约束：(student_id, course_id) 唯一
"""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint

from src.db import Base


class CourseEnrollment(Base):
    __tablename__ = "course_enrollment"
    __table_args__ = (UniqueConstraint("student_id", "course_id", name="uk_student_course"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    enrolled_at = Column(DateTime, default=datetime.now)
