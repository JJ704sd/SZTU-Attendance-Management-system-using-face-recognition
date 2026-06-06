"""
tests/test_course_enrollment_dao.py — 选课 DAO 单测

注意：course_enrollment.course_id 是 FK → course.id。
测试 fixture 会创建一个真 course 行，避免 FK 约束失败。
"""
import uuid

import pytest

from src.dao.course_enrollment_dao import CourseEnrollmentDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.course import Course


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def student_and_course():
    """注册一个临时学生 + 建一个临时课程，测试后清理。"""
    from src.services.auth_service import AuthService
    user = AuthService().register(
        username=_uni("s"),
        password="123456",
        real_name="选课测试",
        role="student",
        student_id=_uni("sid"),
    )
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="测试课",
            course_type="theory",
            teacher_id=user.id,  # 自引用（student 也当 teacher，FK 仍满足）
        )
        s.add(course)
        s.flush()
        course_id = course.id
    yield user.id, course_id
    # 清理
    with session_scope() as s:
        s.query(CourseEnrollmentDao.model).filter(
            CourseEnrollmentDao.model.student_id == user.id).delete()
        s.query(Course).filter(Course.id == course_id).delete()
        s.query(UserDao.model).filter(UserDao.model.id == user.id).delete()


def test_enroll_and_find_one(student_and_course):
    student_id, course_id = student_and_course
    with session_scope() as s:
        dao = CourseEnrollmentDao(s)
        enrollment_id = dao.enroll(student_id, course_id)
        assert enrollment_id > 0
        found = dao.find_one(student_id, course_id)
        assert found is not None
        assert found.id == enrollment_id


def test_find_by_student(student_and_course):
    student_id, course_id = student_and_course
    # 多建一个 course 给同一个 student 选
    with session_scope() as s:
        course2 = Course(
            course_code=_uni("C"),
            course_name="测试课2",
            course_type="theory",
            teacher_id=student_id,
        )
        s.add(course2)
        s.flush()
        course2_id = course2.id
    try:
        with session_scope() as s:
            dao = CourseEnrollmentDao(s)
            dao.enroll(student_id, course_id)
            dao.enroll(student_id, course2_id)
            rows = dao.find_by_student(student_id)
            assert len(rows) == 2
            course_ids = {r.course_id for r in rows}
            assert course_ids == {course_id, course2_id}
    finally:
        with session_scope() as s:
            s.query(CourseEnrollmentDao.model).filter(
                CourseEnrollmentDao.model.student_id == student_id).delete()
            s.query(Course).filter(Course.id == course2_id).delete()


def test_unenroll(student_and_course):
    student_id, course_id = student_and_course
    with session_scope() as s:
        dao = CourseEnrollmentDao(s)
        dao.enroll(student_id, course_id)
        assert dao.find_one(student_id, course_id) is not None
        n = dao.unenroll(student_id, course_id)
        assert n == 1
        assert dao.find_one(student_id, course_id) is None


def test_enroll_idempotent(student_and_course):
    """enroll 重复调用应该返回同一行（不抛 unique 约束）。"""
    student_id, course_id = student_and_course
    with session_scope() as s:
        dao = CourseEnrollmentDao(s)
        id1 = dao.enroll(student_id, course_id)
        id2 = dao.enroll(student_id, course_id)
        assert id1 == id2

