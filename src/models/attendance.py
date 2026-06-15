"""
models/attendance.py — 考勤任务、记录、请假
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Text,
    ForeignKey, Enum, UniqueConstraint,
)

from src.db import Base


class AttendanceTask(Base):
    __tablename__ = "attendance_task"

    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Integer, ForeignKey("course.id"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    classroom_id = Column(Integer, ForeignKey("classroom.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum("open", "closed", name="task_status"), default="open")
    created_at = Column(DateTime, default=datetime.now)


class AttendanceRecord(Base):
    __tablename__ = "attendance_record"
    __table_args__ = (UniqueConstraint("task_id", "student_id", name="uk_task_student"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("attendance_task.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    sign_in_time = Column(DateTime)
    status = Column(
        Enum("present", "late", "absent", "leave", name="att_status"),
        default="absent",
    )
    match_score = Column(Float)
    face_image = Column(String(255))
    # W13+: 区分刷脸 / 数字码 / 二维码签到，便于审计与按方式统计。
    # 默认 'face' 兼容 W12 及更早记录（旧记录不留空即可）。
    signin_method = Column(
        Enum("face", "digit", "qr", name="signin_method"),
        default="face",
    )
    created_at = Column(DateTime, default=datetime.now)


class LeaveRequest(Base):
    __tablename__ = "leave_request"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("attendance_task.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        Enum("pending", "approved", "rejected", name="leave_status"),
        default="pending",
    )
    approver_id = Column(Integer, ForeignKey("user.id"))
    approve_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
