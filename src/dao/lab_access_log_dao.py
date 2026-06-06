"""
dao/lab_access_log_dao.py — 实验室准入日志 DAO

W4 用途：
- 记录每次准入尝试（放行/拒绝）
- admin 端"准入日志"Tab 展示
- report_service 实验室使用率统计
"""
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import desc

from src.dao.base import BaseDao
from src.models.lab import LabAccessLog


class LabAccessLogDao(BaseDao[LabAccessLog]):
    model = LabAccessLog

    def log_attempt(self, lab_id: int, granted: bool, reason: str = None,
                    student_id: Optional[int] = None,
                    face_image: Optional[str] = None,
                    access_time: Optional[datetime] = None) -> int:
        """记一次准入尝试，返回新行 id。

        access_time: 可选；不传则用 LabAccessLog.access_time 的 default (datetime.now)。
        传了则用传入的时间（测试场景需要控时间用）。"""
        row = LabAccessLog(
            student_id=student_id,
            lab_id=lab_id,
            granted=1 if granted else 0,
            reason=reason,
            face_image=face_image,
        )
        if access_time is not None:
            row.access_time = access_time
        self.s.add(row)
        self.s.flush()
        return row.id

    def find_by_lab(self, lab_id: int, limit: int = 100) -> List[LabAccessLog]:
        """某实验室最近的准入记录，按时间倒序。
        ⚠️ MySQL DATETIME 默认精度只到秒, 同一秒插入的多条记录 order by access_time
        desc 排序不稳定 → 加 id DESC 作 tie-breaker 保证确定性.
        """
        return self.s.query(LabAccessLog).filter(
            LabAccessLog.lab_id == lab_id,
        ).order_by(desc(LabAccessLog.access_time), desc(LabAccessLog.id)).limit(limit).all()

    def find_by_student(self, student_id: int, limit: int = 100) -> List[LabAccessLog]:
        """某学生最近的准入记录。
        ⚠️ 同 find_by_lab: 加 id DESC 兜底 MySQL 同秒时间戳 tie-break.
        """
        return self.s.query(LabAccessLog).filter(
            LabAccessLog.student_id == student_id,
        ).order_by(desc(LabAccessLog.access_time), desc(LabAccessLog.id)).limit(limit).all()

    def count_recent_grants(self, lab_id: int, since_minutes: int = 60) -> int:
        """某实验室最近 N 分钟放行次数（用于使用率统计）。"""
        since = datetime.now() - timedelta(minutes=since_minutes)
        return self.s.query(LabAccessLog).filter(
            LabAccessLog.lab_id == lab_id,
            LabAccessLog.access_time >= since,
            LabAccessLog.granted == 1,
        ).count()
