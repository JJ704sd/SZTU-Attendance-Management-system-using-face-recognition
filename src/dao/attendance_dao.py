"""
dao/attendance_dao.py — 考勤相关 DAO
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from src.dao.base import BaseDao
from src.models.attendance import AttendanceTask, AttendanceRecord, LeaveRequest


class AttendanceTaskDao(BaseDao[AttendanceTask]):
    model = AttendanceTask

    def find_by_id(self, task_id: int) -> Optional[AttendanceTask]:
        return self.s.query(AttendanceTask).get(task_id)

    def find_by_teacher(self, teacher_id: int) -> List[AttendanceTask]:
        return self.s.query(AttendanceTask).filter(
            AttendanceTask.teacher_id == teacher_id
        ).order_by(desc(AttendanceTask.start_time)).all()

    def find_open_tasks(self) -> List[AttendanceTask]:
        return self.s.query(AttendanceTask).filter(
            AttendanceTask.status == "open"
        ).all()


class AttendanceRecordDao(BaseDao[AttendanceRecord]):
    model = AttendanceRecord

    def find_by_task(self, task_id: int) -> List[AttendanceRecord]:
        return self.s.query(AttendanceRecord).filter(
            AttendanceRecord.task_id == task_id
        ).all()

    def find_student_record(self, task_id: int, student_id: int) -> Optional[AttendanceRecord]:
        return self.s.query(AttendanceRecord).filter(
            and_(
                AttendanceRecord.task_id == task_id,
                AttendanceRecord.student_id == student_id,
            )
        ).first()

    def count_by_status(self, task_id: int) -> dict:
        rows = self.s.query(
            AttendanceRecord.status, AttendanceRecord
        ).filter(AttendanceRecord.task_id == task_id).all()
        from collections import Counter
        return dict(Counter(r[0] for r in rows))


class LeaveRequestDao(BaseDao[LeaveRequest]):
    model = LeaveRequest

    def find_pending(self) -> List[LeaveRequest]:
        return self.s.query(LeaveRequest).filter(
            LeaveRequest.status == "pending"
        ).all()

    def find_by_student_task(self, student_id: int, task_id: int) -> Optional[LeaveRequest]:
        return self.s.query(LeaveRequest).filter(
            and_(
                LeaveRequest.student_id == student_id,
                LeaveRequest.task_id == task_id,
            )
        ).first()
