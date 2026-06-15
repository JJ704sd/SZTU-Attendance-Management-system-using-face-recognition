"""
models/task_signin_code.py — 签到码（数字 / 二维码）

W13+ 引入，对分易风格的「教师手生成 → 学生提交码」签到链路：
- digit: 4 位纯数字，{0:04d} 补前导零
- qr: 22 字符 base64 token（secrets.token_urlsafe(16)）

教师每次「🎲 生成新码」都失效同任务同类型旧码（is_active=0）后插入一条新码。
学生签到校验三件套：is_active=1 + 未过期 + code_value 一致，任一不满足返 None。
"""
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, DateTime, Enum, ForeignKey, Index,
)

from src.db import Base


class TaskSigninCode(Base):
    __tablename__ = "task_signin_code"
    __table_args__ = (
        Index("idx_task_type_active", "task_id", "code_type", "is_active"),
        Index("idx_expiry", "expires_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(
        Integer,
        ForeignKey("attendance_task.id", ondelete="CASCADE"),
        nullable=False,
    )
    code_type = Column(
        Enum("digit", "qr", name="code_type"),
        nullable=False,
    )
    code_value = Column(String(64), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
