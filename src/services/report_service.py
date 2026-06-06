"""
services/report_service.py — 报表服务

W4 Phase 3d: 4 个查询方法给 admin/teacher 报表用
- attendance_rate_per_student: 学生出勤率排行
- attendance_trend_per_course: 课程每日出勤率趋势
- lab_usage_rate: 实验室使用率（按小时聚合）
- absent_warning_list: 出勤率低于阈值的学生预警

出勤率定义: (present + late) / (present + late + absent + leave)
late 算"出勤"是因为人到了（只是迟到）；absent 是没到；leave 是请假。
"""
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask
from src.models.lab import LabAccessLog
from src.models.user import User

log = logging.getLogger(__name__)


@dataclass
class StudentRate:
    student_id: int
    real_name: str
    rate: float  # 0-1


@dataclass
class TrendPoint:
    date: date
    rate: float


@dataclass
class LabUsagePoint:
    date: date
    hour: int
    count: int


@dataclass
class AbsentWarning:
    student_id: int
    real_name: str
    rate: float
    course_name: str  # "（全部课程）" 或具体课程名


class ReportService:
    """报表查询（只读，不写 DB）。"""

    @staticmethod
    def _compute_rate(records) -> float:
        if not records:
            return 0.0
        attended = sum(1 for r in records if r.status in ("present", "late"))
        return attended / len(records)

    def attendance_rate_per_student(
        self, course_id: Optional[int] = None,
    ) -> List[StudentRate]:
        """某课程（course_id 给定）或跨所有课程（None）的学生出勤率排行。

        出勤率 = (present + late) / total_records"""
        with session_scope() as s:
            q = s.query(AttendanceRecord)
            if course_id is not None:
                q = q.join(AttendanceTask).filter(
                    AttendanceTask.course_id == course_id,
                )
            records = q.all()

            per_student: dict[int, list] = defaultdict(list)
            for r in records:
                per_student[r.student_id].append(r)

            result = []
            for sid, stu_records in per_student.items():
                rate = self._compute_rate(stu_records)
                user = UserDao(s).get(sid)
                real_name = user.real_name if user else f"#{sid}"
                result.append(StudentRate(
                    student_id=sid, real_name=real_name, rate=rate,
                ))

            result.sort(key=lambda x: x.rate, reverse=True)
            return result

    def attendance_trend_per_course(
        self, course_id: int, days: int = 30,
    ) -> List[TrendPoint]:
        """某课程最近 N 天每日出勤率。

        设计: 按 AttendanceTask.start_time 分组（一个 task = 一天数据），
        不用 AttendanceRecord.sign_in_time —— 因为 absent/leave 的 sign_in_time
        为 None，按 sign_in_time 分组会漏掉这些"未签到"的状态。

        出勤率 = (present + late) / total_in_task
        """
        with session_scope() as s:
            since = datetime.now() - timedelta(days=days)
            tasks = (
                s.query(AttendanceTask)
                .filter(
                    AttendanceTask.course_id == course_id,
                    AttendanceTask.start_time >= since,
                )
                .all()
            )
            if not tasks:
                return []

            task_ids = [t.id for t in tasks]
            records = (
                s.query(AttendanceRecord)
                .filter(AttendanceRecord.task_id.in_(task_ids))
                .all()
            )

            # task_id -> date 映射
            task_to_date = {t.id: t.start_time.date() for t in tasks}

            # 按 (date) 聚合 records
            per_day: dict[date, list] = defaultdict(list)
            for r in records:
                d = task_to_date.get(r.task_id)
                if d is not None:
                    per_day[d].append(r)

            result = []
            for d in sorted(per_day.keys()):
                rate = self._compute_rate(per_day[d])
                result.append(TrendPoint(date=d, rate=rate))
            return result

    def lab_usage_rate(
        self, lab_id: int, days: int = 7,
    ) -> List[LabUsagePoint]:
        """某实验室最近 N 天（按小时聚合）的放行次数。"""
        with session_scope() as s:
            since = datetime.now() - timedelta(days=days)
            logs = (
                s.query(LabAccessLog)
                .filter(
                    LabAccessLog.lab_id == lab_id,
                    LabAccessLog.access_time >= since,
                    LabAccessLog.granted == 1,  # 只算放行
                )
                .all()
            )

            per_dh: dict[tuple[date, int], int] = defaultdict(int)
            for log in logs:
                d = log.access_time.date()
                h = log.access_time.hour
                per_dh[(d, h)] += 1

            result = []
            for (d, h), count in sorted(per_dh.items()):
                result.append(LabUsagePoint(date=d, hour=h, count=count))
            return result

    def absent_warning_list(
        self, threshold: float = 0.8,
    ) -> List[AbsentWarning]:
        """出勤率 < threshold 的学生清单（跨所有课程聚合），按出勤率升序。

        threshold 默认 0.8（出勤率低于 80% 触发预警）。
        """
        # 复用 attendance_rate_per_student
        all_rates = self.attendance_rate_per_student(course_id=None)

        # 只取 < threshold 的，并加 course_name 字段
        warnings = []
        for r in all_rates:
            if r.rate < threshold:
                warnings.append(AbsentWarning(
                    student_id=r.student_id,
                    real_name=r.real_name,
                    rate=r.rate,
                    course_name="（全部课程）",
                ))
        # 按出勤率升序（最差的排前）
        warnings.sort(key=lambda x: x.rate)
        return warnings
