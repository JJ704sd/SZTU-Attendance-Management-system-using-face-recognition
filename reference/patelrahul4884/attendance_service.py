"""
attendance_service.py — 考勤任务与签到服务
"""

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import and_

from models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest
from models.user import User
from models.course import Course

# 迟到判定：开始时间后 10 分钟
LATE_THRESHOLD_MINUTES = 10


class AttendanceService:
    def __init__(self, db_session, face_service):
        self.db = db_session
        self.face = face_service

    # -----------------------------------------------------
    # 教师创建考勤任务
    # -----------------------------------------------------
    def create_task(self, course_id: int, teacher_id: int, classroom_id: int,
                    start_time: datetime, end_time: datetime) -> int:
        """返回新任务 id"""
        task = AttendanceTask(
            course_id=course_id,
            teacher_id=teacher_id,
            classroom_id=classroom_id,
            start_time=start_time,
            end_time=end_time,
            status="open",
        )
        self.db.add(task)
        self.db.commit()
        return task.id

    # -----------------------------------------------------
    # 学生刷脸签到（核心）
    # -----------------------------------------------------
    def sign_in_by_face(self, task_id: int, user_id: int,
                        match_distance: float) -> Optional[AttendanceRecord]:
        """
        学生刷脸后调用：
        1. 检查任务是否开放
        2. 检查是否重复签到
        3. 判断 present / late
        4. 写记录
        """
        task = self.db.query(AttendanceTask).get(task_id)
        if not task or task.status != "open":
            return None

        # 查是否已签到
        existed = self.db.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.task_id == task_id,
                AttendanceRecord.student_id == user_id,
            )
        ).first()
        if existed:
            return None  # 已签到，幂等

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
        self.db.add(record)
        self.db.commit()
        return record

    # -----------------------------------------------------
    # 任务结束：自动标记缺勤
    # -----------------------------------------------------
    def close_task_and_mark_absent(self, task_id: int):
        """end_time 到达后调用，遍历课程学生名单补齐缺勤"""
        task = self.db.query(AttendanceTask).get(task_id)
        if not task:
            return
        task.status = "closed"

        # 拿课程所有学生（这里简化为 role='student' 的所有，实际应关联选课表）
        students = self.db.query(User).filter(User.role == "student").all()
        for s in students:
            existed = self.db.query(AttendanceRecord).filter(
                and_(AttendanceRecord.task_id == task_id,
                     AttendanceRecord.student_id == s.id)
            ).first()
            if existed:
                continue

            # 查是否有通过的请假
            leave = self.db.query(LeaveRequest).filter(
                and_(LeaveRequest.task_id == task_id,
                     LeaveRequest.student_id == s.id,
                     LeaveRequest.status == "approved")
            ).first()
            status = "leave" if leave else "absent"

            self.db.add(AttendanceRecord(
                task_id=task_id,
                student_id=s.id,
                sign_in_time=None,
                status=status,
            ))
        self.db.commit()

    # -----------------------------------------------------
    # 请假申请
    # -----------------------------------------------------
    def apply_leave(self, student_id: int, task_id: int, reason: str) -> int:
        req = LeaveRequest(
            student_id=student_id,
            task_id=task_id,
            reason=reason,
            status="pending",
        )
        self.db.add(req)
        self.db.commit()
        return req.id

    def approve_leave(self, leave_id: int, approver_id: int, approved: bool):
        req = self.db.query(LeaveRequest).get(leave_id)
        if not req:
            return
        req.status = "approved" if approved else "rejected"
        req.approver_id = approver_id
        req.approve_time = datetime.now()
        self.db.commit()
