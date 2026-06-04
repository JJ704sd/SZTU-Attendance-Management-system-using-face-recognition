"""
lab_access_service.py — 实验室准入权限校验
差异化亮点：把人脸识别 + 安全培训有效性 + 实验室等级三者联动。
"""

from datetime import date
from typing import Tuple

from models.user import User
from models.lab import Laboratory, LabTraining, LabAccessLog


class LabAccessService:
    def __init__(self, db_session):
        self.db = db_session

    # -----------------------------------------------------
    # 准入核验：返回 (granted, reason)
    # -----------------------------------------------------
    def check_access(self, user_id: int, lab_id: int,
                     face_match_distance: float = 0.0) -> Tuple[bool, str]:
        """
        完整准入流程：
        1. 用户是有效学生
        2. 实验室存在
        3. 人脸识别通过（distance < 0.45）
        4. 有对应的安全培训记录
        5. 培训未过期
        6. 培训类型与实验室要求匹配
        7. 高等级实验室的分数门槛
        """
        # 1. 用户校验
        user = self.db.query(User).get(user_id)
        if not user or user.role != "student":
            self._log(user_id, lab_id, granted=0, reason="非学生用户")
            return False, "非学生用户"

        # 2. 实验室存在
        lab = self.db.query(Laboratory).get(lab_id)
        if not lab:
            return False, "实验室不存在"

        # 3. 人脸识别
        if face_match_distance > 0.45:
            self._log(user_id, lab_id, granted=0, reason="人脸识别未通过")
            return False, "人脸识别未通过"

        # 4 & 5 & 6 & 7. 培训记录核验
        training = self.db.query(LabTraining).filter(
            LabTraining.student_id == user_id,
            LabTraining.lab_id == lab_id,
        ).first()

        if not training:
            self._log(user_id, lab_id, granted=0,
                      reason=f"未完成{lab.required_training}类安全培训")
            return False, f"未完成{lab.required_training}类安全培训"

        if training.expiry_date < date.today():
            self._log(user_id, lab_id, granted=0, reason="安全培训已过期")
            return False, "安全培训已过期，请重新培训"

        if (training.training_type != lab.required_training):
            self._log(user_id, lab_id, granted=0, reason="培训类型与实验室要求不匹配")
            return False, f"需要{lab.required_training}类培训，当前为{training.training_type}类"

        # 高等级实验室分数门槛
        if lab.safety_level >= 4 and training.score < 90:
            self._log(user_id, lab_id, granted=0,
                      reason=f"高等级实验室(safety_level={lab.safety_level})要求分数≥90")
            return False, f"高等级实验室要求分数≥90，当前{training.score}"

        if lab.safety_level == 3 and training.score < 80:
            self._log(user_id, lab_id, granted=0, reason="等级3实验室要求分数≥80")
            return False, f"等级3实验室要求分数≥80，当前{training.score}"

        # 全部通过
        self._log(user_id, lab_id, granted=1, reason="准入通过")
        return True, "准入通过"

    def _log(self, user_id: int, lab_id: int, granted: int, reason: str):
        """写准入日志（无论通过拒绝都记，便于审计）"""
        log = LabAccessLog(
            student_id=user_id,
            lab_id=lab_id,
            granted=granted,
            reason=reason,
        )
        self.db.add(log)
        self.db.commit()
