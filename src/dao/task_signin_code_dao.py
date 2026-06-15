"""
dao/task_signin_code_dao.py — 签到码数据访问层

封装 TaskSigninCode 表的 CRUD + 业务相关查询：
- insert_new: 写一条新码
- find_active_by_task_type: 查某任务某类型的当前有效码（可能多条，按时间倒序）
- find_active_by_value: 按 code_value 查有效码（学生签到校验）
- deactivate_active_for_task_type: 同任务同类型所有未过期旧码 is_active=0
  （generate_signin_code 调，覆盖式失效）

⚠️ 边界校验：
  本 DAO 假定 caller 已校验业务规则（task 存在 + status=open）。
  本层不重复校验，但每条查询都明确过滤 is_active=1 + expires_at>now，
  避免外层误读到失效码。
"""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import and_, desc

from src.dao.base import BaseDao
from src.models.task_signin_code import TaskSigninCode


class TaskSigninCodeDao(BaseDao[TaskSigninCode]):
    model = TaskSigninCode

    # ---------- 写 ----------
    def insert_new(self, task_id: int, code_type: str, code_value: str,
                   expires_at: datetime) -> TaskSigninCode:
        """插入一条新码。caller 应在事务内先调 deactivate_active_for_task_type。"""
        obj = TaskSigninCode(
            task_id=task_id,
            code_type=code_type,
            code_value=code_value,
            expires_at=expires_at,
            is_active=1,
        )
        self.s.add(obj)
        self.s.flush()
        return obj

    def deactivate_active_for_task_type(self, task_id: int, code_type: str,
                                         now: Optional[datetime] = None) -> int:
        """把同任务同类型的所有未过期有效码 is_active=0，返回受影响行数。
        用于「教师生成新码前失效旧码」。"""
        now = now or datetime.now()
        result = self.s.query(TaskSigninCode).filter(
            and_(
                TaskSigninCode.task_id == task_id,
                TaskSigninCode.code_type == code_type,
                TaskSigninCode.is_active == 1,
                TaskSigninCode.expires_at > now,
            )
        ).update({TaskSigninCode.is_active: 0}, synchronize_session=False)
        return result

    # ---------- 读 ----------
    def find_active_by_value(self, task_id: int, code_type: str,
                             code_value: str) -> Optional[TaskSigninCode]:
        """按 task + type + value 查「当前有效」码。
        有效 = is_active=1 且 expires_at > now。
        学生签到校验的核心查询。
        """
        return self.s.query(TaskSigninCode).filter(
            and_(
                TaskSigninCode.task_id == task_id,
                TaskSigninCode.code_type == code_type,
                TaskSigninCode.code_value == code_value,
                TaskSigninCode.is_active == 1,
                TaskSigninCode.expires_at > datetime.now(),
            )
        ).order_by(desc(TaskSigninCode.created_at)).first()

    def find_active_by_task_type(self, task_id: int, code_type: str) -> List[TaskSigninCode]:
        """教师端码显示 widget 调：拿当前同类型最新有效码。"""
        return self.s.query(TaskSigninCode).filter(
            and_(
                TaskSigninCode.task_id == task_id,
                TaskSigninCode.code_type == code_type,
                TaskSigninCode.is_active == 1,
                TaskSigninCode.expires_at > datetime.now(),
            )
        ).order_by(desc(TaskSigninCode.created_at)).all()
