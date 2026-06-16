"""
models/course_teacher.py — 课程-教师 多对多关联 (W14+)

背景: xls 课表里有 3 门课是多老师 (信号与系统 / 数据库原理 / 医用电子技术),
      之前的 Course.teacher_id 是单 FK 容纳不下. 加本表存所有任课教师.

设计:
    - 保留 Course.teacher_id 作为 "主讲教师" (兼容现有 attendance_task 业务)
    - 本表存所有任课教师: 第一条 role='main' (主讲), 其余 role='assistant'
    - 多老师课程所有教师都进本表
"""
from datetime import datetime
from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum, UniqueConstraint

from src.db import Base


class CourseTeacher(Base):
    __tablename__ = "course_teacher"
    __table_args__ = (UniqueConstraint("course_id", "teacher_id", name="uk_course_teacher"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("course.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    role = Column(
        Enum("main", "assistant", name="course_teacher_role"),
        nullable=False,
        default="main",
        comment="主讲 (main) / 助教 (assistant)",
    )
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<CourseTeacher course_id={self.course_id} teacher_id={self.teacher_id} role={self.role}>"
