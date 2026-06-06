"""
dao/lab_dao.py — 实验室 DAO

Laboratory model 在 src/models/course.py 里（早期设计延续）
"""
from typing import List, Optional

from src.dao.base import BaseDao
from src.models.course import Laboratory


class LabDao(BaseDao[Laboratory]):
    model = Laboratory

    def find_all(self) -> List[Laboratory]:
        return self.s.query(Laboratory).order_by(Laboratory.id).all()

    def find_by_id(self, lab_id: int) -> Optional[Laboratory]:
        return self.s.get(Laboratory, lab_id)

    def find_by_safety_level(self, level: int) -> List[Laboratory]:
        """某安全等级的所有实验室。"""
        return self.s.query(Laboratory).filter(
            Laboratory.safety_level == level
        ).all()
