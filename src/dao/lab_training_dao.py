"""
dao/lab_training_dao.py — 安全培训记录 DAO

W4 用途：lab_access_service.check_access 查询 user 是否在该 lab 有有效培训
"""
from datetime import date
from typing import List, Optional

from src.dao.base import BaseDao
from src.models.lab import LabTraining


class LabTrainingDao(BaseDao[LabTraining]):
    model = LabTraining

    def find_by_student(self, student_id: int) -> List[LabTraining]:
        return self.s.query(LabTraining).filter(
            LabTraining.student_id == student_id
        ).all()

    def find_by_student_lab(self, student_id: int, lab_id: int) -> List[LabTraining]:
        """某学生某实验室的所有培训记录（可能多条：重训、过期重做等）。"""
        return self.s.query(LabTraining).filter(
            LabTraining.student_id == student_id,
            LabTraining.lab_id == lab_id,
        ).all()

    def find_valid_by_student_lab(self, student_id: int, lab_id: int,
                                   today: date) -> Optional[LabTraining]:
        """某学生某实验室"当前有效"（expiry_date >= today）的培训记录。

        如果有多个，取最新一条（按 expiry_date DESC）。"""
        return self.s.query(LabTraining).filter(
            LabTraining.student_id == student_id,
            LabTraining.lab_id == lab_id,
            LabTraining.expiry_date >= today,
        ).order_by(LabTraining.expiry_date.desc()).first()
