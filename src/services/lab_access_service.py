"""
services/lab_access_service.py — 实验室准入服务

W4 Phase 3c: 学生刷脸到实验室门口 → 调 check_access 决定放不放行。

设计（跟 WORKFLOWS.md 流程 3 对齐）:

通过分支:
- role != student（教师/管理员）→ 自由出入
- role=student + 有有效培训（未过期 + 类型匹配 + 分数够）→ 放行

拒绝分支:
- role=student 无培训记录 → "未完成{required}安全培训"
- 培训过期 → "安全培训已过期，请重新培训"
- 培训类型与实验室 required_training 不匹配 → "培训类型不匹配"
- 实验室 safety_level >= 4 + score < 90 → "高等级实验室要求分数≥90"

每次结果都写 lab_access_log（审计追溯）。
"""
import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from src.dao.lab_access_log_dao import LabAccessLogDao
from src.dao.lab_dao import LabDao
from src.dao.lab_training_dao import LabTrainingDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.user import User

log = logging.getLogger(__name__)


@dataclass
class AccessResult:
    """准入检查结果。granted=True 放行，False 拒绝；reason 是原因/说明。"""
    granted: bool
    reason: str


class LabAccessService:
    """实验室准入检查。"""

    def check_access(self, user_id: int, lab_id: int) -> AccessResult:
        """检查用户能否进入实验室。返回 AccessResult + 写 lab_access_log。

        业务规则（拒绝优先级从高到低）:
        1. 用户/实验室不存在 → granted=False（异常，不写 log 因为 FK）
        2. role != student → 放行
        3. role=student 无培训记录 → 拒绝（未完成）
        4. 有培训但过期 → 拒绝（已过期）
        5. 培训类型不匹配 → 拒绝
        6. 高等级 + 分数不够 → 拒绝
        7. 全部通过 → 放行
        """
        with session_scope() as s:
            user = UserDao(s).get(user_id)
            lab = LabDao(s).find_by_id(lab_id)

            # 1. 异常：用户或实验室不存在
            if not user or not lab:
                reason = "用户或实验室不存在"
                log.warning("准入检查异常: user_id=%s lab_id=%s", user_id, lab_id)
                return AccessResult(granted=False, reason=reason)

            # 2. 非学生 → 直接放行（教师/管理员自由出入）
            if user.role != "student":
                reason = f"非学生角色 ({user.role}) 自由出入"
                LabAccessLogDao(s).log_attempt(
                    lab_id, granted=True, student_id=user_id, reason=reason,
                )
                return AccessResult(granted=True, reason=reason)

            # 3-4. 学生 → 查培训
            today = date.today()
            training = LabTrainingDao(s).find_valid_by_student_lab(user_id, lab_id, today)

            if not training:
                # 区分无记录 vs 过期
                all_trainings = LabTrainingDao(s).find_by_student_lab(user_id, lab_id)
                if not all_trainings:
                    reason = f"未完成{lab.required_training or '相关'}安全培训"
                else:
                    reason = "安全培训已过期，请重新培训"
                LabAccessLogDao(s).log_attempt(
                    lab_id, granted=False, student_id=user_id, reason=reason,
                )
                return AccessResult(granted=False, reason=reason)

            # 5. 培训类型不匹配
            if lab.required_training and training.training_type != lab.required_training:
                reason = (
                    f"培训类型不匹配（实验室要求 {lab.required_training}，"
                    f"你持 {training.training_type}）"
                )
                LabAccessLogDao(s).log_attempt(
                    lab_id, granted=False, student_id=user_id, reason=reason,
                )
                return AccessResult(granted=False, reason=reason)

            # 6. 高等级 + 分数不够
            if lab.safety_level >= 4 and training.score < 90:
                reason = (
                    f"高等级实验室（safety_level={lab.safety_level}）要求分数≥90，"
                    f"你的分数 {training.score}"
                )
                LabAccessLogDao(s).log_attempt(
                    lab_id, granted=False, student_id=user_id, reason=reason,
                )
                return AccessResult(granted=False, reason=reason)

            # 7. 通过
            reason = (
                f"通过：{training.training_type} 培训，"
                f"分数 {training.score}，safety_level={lab.safety_level}"
            )
            LabAccessLogDao(s).log_attempt(
                lab_id, granted=True, student_id=user_id, reason=reason,
            )
            return AccessResult(granted=True, reason=reason)
