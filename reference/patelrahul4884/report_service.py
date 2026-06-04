"""
report_service.py — 考勤与实验室使用率报表
依赖：matplotlib 3.7+
"""

from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use("Agg")  # 非 GUI 后端，PyQt5 嵌入时改用 FigureCanvas
plt.rcParams["font.sans-serif"] = ["SimHei"]  # 中文显示
plt.rcParams["axes.unicode_minus"] = False

from sqlalchemy import func, and_
from models.attendance import AttendanceTask, AttendanceRecord
from models.user import User
from models.lab import Laboratory, LabAccessLog


class ReportService:
    def __init__(self, db_session):
        self.db = db_session

    # -----------------------------------------------------
    # 1. 学生个人出勤率（最近 N 天）
    # -----------------------------------------------------
    def student_attendance_rate(self, student_id: int, days: int = 30) -> float:
        """返回出勤率（0~1），present+late 都算出勤"""
        since = datetime.now() - timedelta(days=days)
        total = self.db.query(func.count(AttendanceRecord.id)).join(
            AttendanceTask, AttendanceRecord.task_id == AttendanceTask.id
        ).filter(
            AttendanceRecord.student_id == student_id,
            AttendanceTask.start_time >= since,
        ).scalar() or 0
        if total == 0:
            return 0.0
        present = self.db.query(func.count(AttendanceRecord.id)).join(
            AttendanceTask, AttendanceRecord.task_id == AttendanceTask.id
        ).filter(
            AttendanceRecord.student_id == student_id,
            AttendanceTask.start_time >= since,
            AttendanceRecord.status.in_(["present", "late", "leave"]),
        ).scalar() or 0
        return present / total

    # -----------------------------------------------------
    # 2. 班级出勤率排行（柱状图）
    # -----------------------------------------------------
    def class_attendance_bar(self, course_id: int, output_path: str):
        """
        生成某课程下所有学生出勤率柱状图
        """
        records = self.db.query(
            User.real_name,
            AttendanceRecord.status,
        ).join(AttendanceRecord, AttendanceRecord.student_id == User.id).join(
            AttendanceTask, AttendanceTask.id == AttendanceRecord.task_id
        ).filter(AttendanceTask.course_id == course_id).all()

        stat = defaultdict(lambda: {"total": 0, "present": 0})
        for name, status in records:
            stat[name]["total"] += 1
            if status in ("present", "late", "leave"):
                stat[name]["present"] += 1
        names = list(stat.keys())
        rates = [stat[n]["present"] / stat[n]["total"] if stat[n]["total"] else 0
                 for n in names]

        plt.figure(figsize=(10, 5))
        plt.bar(names, rates)
        plt.ylabel("出勤率")
        plt.title(f"课程 {course_id} 学生出勤率")
        plt.xticks(rotation=45)
        plt.ylim(0, 1.1)
        plt.tight_layout()
        plt.savefig(output_path, dpi=120)
        plt.close()

    # -----------------------------------------------------
    # 3. 实验室使用率（按小时热力数据）
    # -----------------------------------------------------
    def lab_usage_summary(self, days: int = 30) -> dict:
        """返回 {lab_id: {hour: count}} 字典，供热力图使用"""
        since = datetime.now() - timedelta(days=days)
        logs = self.db.query(LabAccessLog).filter(
            LabAccessLog.access_time >= since,
            LabAccessLog.granted == 1,
        ).all()

        result = defaultdict(lambda: defaultdict(int))
        for log in logs:
            hour = log.access_time.hour
            result[log.lab_id][hour] += 1
        return dict(result)

    # -----------------------------------------------------
    # 4. 缺勤预警名单（出勤率 < 80%）
    # -----------------------------------------------------
    def absent_warning_list(self, days: int = 30, threshold: float = 0.8) -> list:
        """返回 [(student_id, real_name, rate)] 列表"""
        students = self.db.query(User).filter(User.role == "student").all()
        warnings = []
        for s in students:
            rate = self.student_attendance_rate(s.id, days)
            if 0 < rate < threshold:
                warnings.append((s.id, s.real_name, round(rate, 3)))
        # 按出勤率升序
        warnings.sort(key=lambda x: x[2])
        return warnings
