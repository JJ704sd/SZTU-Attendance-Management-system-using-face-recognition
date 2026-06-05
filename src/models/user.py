"""
models/user.py — 用户表模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Enum, DateTime, SmallInteger

from src.db import Base


class User(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, comment="登录用户名")
    password_hash = Column(String(255), nullable=False, comment="bcrypt 哈希")
    real_name = Column(String(50), nullable=False, comment="真实姓名")
    role = Column(
        Enum("student", "teacher", "lab_admin", name="user_role"),
        nullable=False,
        comment="角色",
    )
    student_id = Column(String(20), unique=True, comment="学号（学生专用）")
    direction = Column(String(50), comment="专业方向")
    email = Column(String(100))
    phone = Column(String(20))
    avatar_path = Column(String(255))
    is_active = Column(SmallInteger, default=1, comment="账号是否启用")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系（按需启用，避免循环导入）
    # face_encodings = relationship("FaceEncoding", back_populates="user", cascade="all, delete-orphan")
    # attendance_records = relationship("AttendanceRecord", back_populates="student")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "real_name": self.real_name,
            "role": self.role,
            "student_id": self.student_id,
            "direction": self.direction,
            "email": self.email,
            "phone": self.phone,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<User {self.id} {self.username} ({self.role})>"
