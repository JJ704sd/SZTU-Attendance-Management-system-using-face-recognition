"""
dao/course_enrollment_dao.py — 选课 DAO

W4 用途：
- close_task_and_mark_absent 改用本表的"选课名单"代替"role=student 全部"
"""
from typing import List, Optional

from src.dao.base import BaseDao
from src.models.course_enrollment import CourseEnrollment


class CourseEnrollmentDao(BaseDao[CourseEnrollment]):
    model = CourseEnrollment

    def find_by_student(self, student_id: int) -> List[CourseEnrollment]:
        return self.s.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == student_id
        ).all()

    def find_by_course(self, course_id: int) -> List[CourseEnrollment]:
        return self.s.query(CourseEnrollment).filter(
            CourseEnrollment.course_id == course_id
        ).all()

    def find_one(self, student_id: int, course_id: int) -> Optional[CourseEnrollment]:
        return self.s.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.course_id == course_id,
        ).first()

    def enroll(self, student_id: int, course_id: int) -> int:
        """新建一条选课记录，返回 id。已存在则直接返回原 id。"""
        existing = self.find_one(student_id, course_id)
        if existing:
            return existing.id
        row = CourseEnrollment(student_id=student_id, course_id=course_id)
        self.s.add(row)
        self.s.flush()
        return row.id

    def unenroll(self, student_id: int, course_id: int) -> int:
        """退课，返回删除行数（0 或 1）。"""
        rows = self.s.query(CourseEnrollment).filter(
            CourseEnrollment.student_id == student_id,
            CourseEnrollment.course_id == course_id,
        ).all()
        n = len(rows)
        for r in rows:
            self.s.delete(r)
        self.s.flush()
        return n
