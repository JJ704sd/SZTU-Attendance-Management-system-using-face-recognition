"""
dao/course_dao.py — 课程 DAO
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from src.dao.base import BaseDao
from src.models.course import Course


class CourseDao(BaseDao[Course]):
    model = Course

    def find_by_code(self, code: str) -> Optional[Course]:
        return self.s.query(Course).filter(Course.course_code == code).first()

    def find_by_teacher(self, teacher_id: int) -> List[Course]:
        return self.s.query(Course).filter(Course.teacher_id == teacher_id).all()

    def find_all(self) -> List[Course]:
        return self.s.query(Course).order_by(Course.course_code).all()
