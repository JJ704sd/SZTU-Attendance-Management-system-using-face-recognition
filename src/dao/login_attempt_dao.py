"""
dao/login_attempt_dao.py — 登录尝试记录 DAO

W4 用途：
- auth_service.login 加 LOGIN_MAX_ATTEMPTS 防暴力破解
- 每次登录记一行；查"最近 N 次失败"判断是否锁定

注意：所有"最近 N 次"按 id DESC 排序（不是 attempted_at DESC），
原因：MySQL DATETIME 默认秒级精度，同事务内多次 INSERT 时间戳相同，
desc 排序不稳定；id 是 PK 自增一定递增，更可靠。
业务语义："最近 5 次"指 5 次独立 attempt，不是 5 个时间点。
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import desc

from src.dao.base import BaseDao
from src.models.login_attempt import LoginAttempt


class LoginAttemptDao(BaseDao[LoginAttempt]):
    model = LoginAttempt

    def record_attempt(self, username: str, success: bool,
                       ip_address: Optional[str] = None) -> int:
        """记一次登录尝试，返回新行 id。"""
        row = LoginAttempt(
            username=username,
            success=1 if success else 0,
            ip_address=ip_address,
        )
        self.s.add(row)
        self.s.flush()
        return row.id

    def count_recent_failures(self, username: str, limit: int = 5) -> int:
        """最近 limit 次（按 id 倒序）中失败次数。"""
        rows = self.s.query(LoginAttempt).filter(
            LoginAttempt.username == username,
        ).order_by(desc(LoginAttempt.id)).limit(limit).all()
        return sum(1 for r in rows if r.success == 0)

    def last_attempt(self, username: str) -> Optional[LoginAttempt]:
        """最后一次登录尝试（按 id 倒序）。"""
        return self.s.query(LoginAttempt).filter(
            LoginAttempt.username == username,
        ).order_by(desc(LoginAttempt.id)).first()

    def clear_attempts(self, username: str) -> int:
        """清空某用户所有登录尝试记录（解锁账号用）。返回删除行数。"""
        rows = self.s.query(LoginAttempt).filter(
            LoginAttempt.username == username,
        ).all()
        n = len(rows)
        for r in rows:
            self.s.delete(r)
        self.s.flush()
        return n

    def find_recent(self, username: str,
                    since_minutes: int = 30) -> List[LoginAttempt]:
        """最近 N 分钟内（按 attempted_at 过滤）的所有尝试，按 id 倒序。

        过滤条件仍用 attempted_at（时间范围）—— N 分钟内这个语义是用户可理解的；
        但排序用 id（稳定）。"""
        since = datetime.now() - timedelta(minutes=since_minutes)
        return self.s.query(LoginAttempt).filter(
            LoginAttempt.username == username,
            LoginAttempt.attempted_at >= since,
        ).order_by(desc(LoginAttempt.id)).all()

