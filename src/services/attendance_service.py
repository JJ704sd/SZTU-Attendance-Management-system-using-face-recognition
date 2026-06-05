"""
services/attendance_service.py — 考勤任务与签到服务
"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_

from src.db import session_scope
from src.models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest
from src.models.user import User

# 迟到判定：开始时间后 10 分钟
LATE_THRESHOLD_MINUTES = 10


class AttendanceService:
    def __init__(self):
        pass  # 每个方法内部用 session_scope

    # -----------------------------------------------------
    # 教师创建考勤任务
    # -----------------------------------------------------
    def create_task(self, course_id: int, teacher_id: int, classroom_id: int,
                    start_time: datetime, end_time: datetime) -> int:
        """返回新任务 id"""
        if end_time <= start_time:
            raise ValueError("结束时间必须晚于开始时间")
        if start_time < datetime.now() - timedelta(minutes=5):
            raise ValueError("开始时间不能早于当前 5 分钟以前")

        with session_scope() as s:
            task = AttendanceTask(
                course_id=course_id,
                teacher_id=teacher_id,
                classroom_id=classroom_id,
                start_time=start_time,
                end_time=end_time,
                status="open",
            )
            s.add(task)
            s.flush()
            return task.id

    # -----------------------------------------------------
    # 学生刷脸签到（核心，后续 face_service 会调）
    # -----------------------------------------------------
    def sign_in_by_face(self, task_id: int, user_id: int,
                        match_distance: float) -> Optional[AttendanceRecord]:
        with session_scope() as s:
            task = s.query(AttendanceTask).get(task_id)
            if not task or task.status != "open":
                return None

            existed = s.query(AttendanceRecord).filter(
                and_(AttendanceRecord.task_id == task_id,
                     AttendanceRecord.student_id == user_id)
            ).first()
            if existed:
                return None

            now = datetime.now()
            late_cutoff = task.start_time + timedelta(minutes=LATE_THRESHOLD_MINUTES)
            status = "present" if now <= late_cutoff else "late"

            record = AttendanceRecord(
                task_id=task_id,
                student_id=user_id,
                sign_in_time=now,
                status=status,
                match_score=match_distance,
            )
            s.add(record)
            s.flush()
            s.refresh(record)
            s.expunge(record)
            return record

    # -----------------------------------------------------
    # 任务结束：自动标记缺勤
    # -----------------------------------------------------
    def close_task_and_mark_absent(self, task_id: int):
        """end_time 到达后调用，遍历课程学生名单补齐缺勤"""
        with session_scope() as s:
            task = s.query(AttendanceTask).get(task_id)
            if not task:
                return
            task.status = "closed"

            # 简化：把 role='student' 的所有用户视为名单
            # 实际应有 course_enrollment 选课表
            students = s.query(User).filter(User.role == "student").all()
            for stu in students:
                existed = s.query(AttendanceRecord).filter(
                    and_(AttendanceRecord.task_id == task_id,
                         AttendanceRecord.student_id == stu.id)
                ).first()
                if existed:
                    continue

                leave = s.query(LeaveRequest).filter(
                    and_(LeaveRequest.task_id == task_id,
                         LeaveRequest.student_id == stu.id,
                         LeaveRequest.status == "approved")
                ).first()
                status = "leave" if leave else "absent"

                s.add(AttendanceRecord(
                    task_id=task_id,
                    student_id=stu.id,
                    sign_in_time=None,
                    status=status,
                ))

    # -----------------------------------------------------
    # 请假申请
    # -----------------------------------------------------
    def apply_leave(self, student_id: int, task_id: int, reason: str) -> int:
        with session_scope() as s:
            req = LeaveRequest(
                student_id=student_id,
                task_id=task_id,
                reason=reason,
                status="pending",
            )
            s.add(req)
            s.flush()
            return req.id

    def approve_leave(self, leave_id: int, approver_id: int, approved: bool):
        with session_scope() as s:
            req = s.query(LeaveRequest).get(leave_id)
            if not req:
                return
            req.status = "approved" if approved else "rejected"
            req.approver_id = approver_id
            req.approve_time = datetime.now()

    # -----------------------------------------------------
    # 统计辅助
    # -----------------------------------------------------
    def task_summary(self, task_id: int) -> dict:
        """返回某个任务的统计：present/late/absent/leave 各多少人"""
        with session_scope() as s:
            from collections import Counter
            rows = s.query(AttendanceRecord.status).filter(
                AttendanceRecord.task_id == task_id
            ).all()
            counter = Counter(r[0] for r in rows)
            return {
                "present": counter.get("present", 0),
                "late": counter.get("late", 0),
                "absent": counter.get("absent", 0),
                "leave": counter.get("leave", 0),
                "total": sum(counter.values()),
            }
