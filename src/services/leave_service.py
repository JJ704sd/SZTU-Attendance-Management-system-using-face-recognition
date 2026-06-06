"""
services/leave_service.py — 请假申请服务

W6 Phase 1: leave_request 流程接入
- student_apply: 学生发起请假
- teacher_review: 老师批/驳
- list_pending_for_task: 老师查某任务下待审批

状态机:
  pending  --approve-->  approved (同时把对应 AttendanceRecord 改 leave)
  pending  --reject--->  rejected
"""
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_

from src.dao.attendance_dao import AttendanceRecordDao
from src.dao.leave_request_dao import LeaveRequestDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.attendance import AttendanceRecord, AttendanceTask, LeaveRequest

log = logging.getLogger(__name__)


class LeaveError(Exception):
    """请假业务异常。"""
    pass


class LeaveService:
    """请假服务。"""

    def student_apply(self, student_id: int, task_id: int, reason: str) -> LeaveRequest:
        """学生发起请假申请。

        校验:
        - 学生存在 + 角色是 student
        - 任务存在 + 状态 open (已结束的课不能补请假)
        - 同一学生同一任务只能有一条 pending 申请

        Returns: 新创建的 LeaveRequest
        Raises: LeaveError (含原因)
        """
        if not reason or not reason.strip():
            raise LeaveError("请假原因不能为空")
        reason = reason.strip()

        with session_scope() as s:
            user = UserDao(s).get(student_id)
            if not user or user.role != "student":
                raise LeaveError(f"用户 {student_id} 不是学生")

            task = s.get(AttendanceTask, task_id)
            if not task:
                raise LeaveError(f"任务 {task_id} 不存在")
            if task.status != "open":
                raise LeaveError(f"任务 {task_id} 已结束 (status={task.status})，不能补请假")

            # 同一学生同一任务只能有一条 pending
            existed = s.query(LeaveRequest).filter(
                and_(
                    LeaveRequest.student_id == student_id,
                    LeaveRequest.task_id == task_id,
                    LeaveRequest.status == "pending",
                )
            ).first()
            if existed:
                raise LeaveError(f"已有 pending 请假申请 (id={existed.id})")

            req = LeaveRequest(
                student_id=student_id,
                task_id=task_id,
                reason=reason,
                status="pending",
            )
            s.add(req)
            s.flush()
            s.refresh(req)
            s.expunge(req)
            log.info("请假申请: student=%s task=%s req_id=%s", student_id, task_id, req.id)
            return req

    def teacher_review(self, request_id: int, approver_id: int,
                      approve: bool, comment: Optional[str] = None) -> LeaveRequest:
        """老师批/驳请假。

        approve=True  → status=approved, 同时把对应 AttendanceRecord 改 leave
        approve=False → status=rejected
        """
        with session_scope() as s:
            req = s.get(LeaveRequest, request_id)
            if not req:
                raise LeaveError(f"请假申请 {request_id} 不存在")
            if req.status != "pending":
                raise LeaveError(f"请假申请 {request_id} 已处理 (status={req.status})")

            approver = UserDao(s).get(approver_id)
            if not approver or approver.role not in ("teacher", "lab_admin"):
                raise LeaveError(f"审批人 {approver_id} 角色无权审批")

            req.status = "approved" if approve else "rejected"
            req.approver_id = approver_id
            req.approve_time = datetime.now()
            # 如果是 approved, 把对应 AttendanceRecord (如有) 改 leave
            if approve:
                rec = s.query(AttendanceRecord).filter(
                    and_(
                        AttendanceRecord.task_id == req.task_id,
                        AttendanceRecord.student_id == req.student_id,
                    )
                ).first()
                if rec:
                    rec.status = "leave"
                    log.info("请假批准: 同步 record id=%s status=leave", rec.id)
                else:
                    # 没有 record (close_task 前): 不创建, 让 close_task 自己补 absent
                    log.info("请假批准: record 不存在, 由 close_task 补")

            s.flush()
            s.refresh(req)
            s.expunge(req)
            log.info("请假审批: req_id=%s status=%s approver=%s",
                     request_id, req.status, approver_id)
            return req

    def list_pending_for_task(self, task_id: int) -> List[LeaveRequest]:
        """老师查某任务下所有待审批的请假。"""
        with session_scope() as s:
            return LeaveRequestDao(s).find_pending_by_task(task_id)

    def list_by_student(self, student_id: int) -> List[LeaveRequest]:
        """查某学生所有请假历史。"""
        with session_scope() as s:
            return LeaveRequestDao(s).find_by_student(student_id)
