"""
dao/leave_request_dao.py — 请假申请 DAO
W6 Phase 1: leave_request 流程接入
"""
from typing import List, Optional

from src.dao.base import BaseDao
from src.models.attendance import LeaveRequest


class LeaveRequestDao(BaseDao[LeaveRequest]):
    model = LeaveRequest

    def find_pending_by_task(self, task_id: int) -> List[LeaveRequest]:
        """某任务下所有待审批的请假申请。"""
        return self.s.query(LeaveRequest).filter(
            LeaveRequest.task_id == task_id,
            LeaveRequest.status == "pending",
        ).all()

    def find_by_student(self, student_id: int) -> List[LeaveRequest]:
        """某学生所有请假申请（按时间倒序）。"""
        return self.s.query(LeaveRequest).filter(
            LeaveRequest.student_id == student_id,
        ).order_by(LeaveRequest.created_at.desc()).all()

    def find_by_task(self, task_id: int) -> List[LeaveRequest]:
        """某任务所有请假申请。"""
        return self.s.query(LeaveRequest).filter(
            LeaveRequest.task_id == task_id,
        ).all()
