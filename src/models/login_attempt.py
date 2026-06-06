"""
models/login_attempt.py — 登录尝试记录

Phase 1 / W4：
- 给 auth_service.login 加 LOGIN_MAX_ATTEMPTS 防暴力破解
- 记录每次登录的用户名/时间/成功/失败/IP
- 查询"最近 N 次失败次数"判断是否锁定
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, SmallInteger

from src.db import Base


class LoginAttempt(Base):
    __tablename__ = "login_attempt"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), nullable=False, comment="登录用户名")
    attempted_at = Column(DateTime, default=datetime.now)
    success = Column(SmallInteger, nullable=False, comment="1成功/0失败")
    ip_address = Column(String(45), comment="IPv4/IPv6")
