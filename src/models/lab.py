"""
models/lab.py — 安全培训 & 实验室准入日志
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, SmallInteger, ForeignKey, Enum

from src.db import Base


class LabTraining(Base):
    __tablename__ = "lab_training"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    lab_id = Column(Integer, ForeignKey("laboratory.id"), nullable=False)
    training_type = Column(
        Enum("生物", "化学", "辐射", "设备", name="training_type"),
        nullable=False,
    )
    completion_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    score = Column(Float, nullable=False)
    instructor_id = Column(Integer, ForeignKey("user.id"))
    created_at = Column(DateTime, default=datetime.now)


class LabAccessLog(Base):
    __tablename__ = "lab_access_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey("user.id"))
    lab_id = Column(Integer, ForeignKey("laboratory.id"), nullable=False)
    access_time = Column(DateTime, default=datetime.now)
    granted = Column(SmallInteger, nullable=False, comment="1放行/0拒绝")
    reason = Column(String(255))
    face_image = Column(String(255))
