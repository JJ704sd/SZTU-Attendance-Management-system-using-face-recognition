"""
dao/course_teacher_dao.py — 课程-教师 关联 DAO (W14+)

配套: src/models/course_teacher.py
"""
from typing import List, Optional

from src.dao.base import BaseDao
from src.models.course_teacher import CourseTeacher


class CourseTeacherDao(BaseDao[CourseTeacher]):
    model = CourseTeacher

    def find_by_course(self, course_id: int) -> List[CourseTeacher]:
        return self.s.query(CourseTeacher).filter(
            CourseTeacher.course_id == course_id
        ).all()

    def find_by_teacher(self, teacher_id: int) -> List[CourseTeacher]:
        return self.s.query(CourseTeacher).filter(
            CourseTeacher.teacher_id == teacher_id
        ).all()

    def find_one(self, course_id: int, teacher_id: int) -> Optional[CourseTeacher]:
        return self.s.query(CourseTeacher).filter(
            CourseTeacher.course_id == course_id,
            CourseTeacher.teacher_id == teacher_id,
        ).first()

    def add(self, course_id: int, teacher_id: int, role: str = "main") -> int:
        """新建关联, 已存在则直接返回原 id (幂等)."""
        existing = self.find_one(course_id, teacher_id)
        if existing:
            return existing.id
        row = CourseTeacher(course_id=course_id, teacher_id=teacher_id, role=role)
        self.s.add(row)
        self.s.flush()
        return row.id
