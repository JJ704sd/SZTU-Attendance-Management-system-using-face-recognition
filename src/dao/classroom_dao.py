"""
dao/classroom_dao.py — 教室 DAO
"""
from typing import List

from src.dao.base import BaseDao
from src.models.course import Classroom


class ClassroomDao(BaseDao[Classroom]):
    model = Classroom

    def find_all(self) -> List[Classroom]:
        return self.s.query(Classroom).order_by(Classroom.name).all()

    def find_with_camera(self) -> List[Classroom]:
        return self.s.query(Classroom).filter(Classroom.has_camera == 1).all()
