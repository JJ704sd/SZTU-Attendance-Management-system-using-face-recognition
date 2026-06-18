"""
tests/test_course_dao.py — CourseDao 单测 (W15+ 回归)

覆盖 W14+ 课程-教师多对多迁移后的 find_by_teacher:
- 主讲老师在 course.teacher_id 里的 → 应该查到（兼容老逻辑）
- 助教老师只在 course_teacher 关联表里的 → **也应该查到**（W14+ 新行为）
- 跟这门课无关的老师 → 查不到
- 主讲 + 助教同时关联同一门课 → DISTINCT 去重，不能返 2 行
"""
import uuid

import pytest

from src.dao.course_dao import CourseDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.course import Course
from src.models.course_teacher import CourseTeacher


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def two_teachers_and_course():
    """建 2 个 teacher 用户 + 1 门课 + 1 条 course_teacher 关联(assistant)。

    第一个老师是 Course.teacher_id (主讲),
    第二个老师只在 course_teacher 关联表里 (助教).
    """
    from src.services.auth_service import AuthService

    main = AuthService().register(
        username=_uni("t"), password="123456", real_name="主讲测试", role="teacher",
    )
    assist = AuthService().register(
        username=_uni("t"), password="123456", real_name="助教测试", role="teacher",
    )
    unrelated = AuthService().register(
        username=_uni("t"), password="123456", real_name="无关测试", role="teacher",
    )

    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="多老师测试课",
            course_type="theory",
            teacher_id=main.id,
        )
        s.add(course)
        s.flush()
        course_id = course.id
        # 关键: 只关联助教, 不动 Course.teacher_id
        s.add(CourseTeacher(course_id=course_id, teacher_id=assist.id, role="assistant"))
        s.flush()

    try:
        yield main.id, assist.id, unrelated.id, course_id
    finally:
        with session_scope() as s:
            s.query(CourseTeacher).filter(CourseTeacher.course_id == course_id).delete()
            s.query(Course).filter(Course.id == course_id).delete()
            s.query(UserDao.model).filter(UserDao.model.id.in_([main.id, assist.id, unrelated.id])).delete()


def test_find_by_teacher_returns_main_teacher_courses(two_teachers_and_course):
    """W14 之前的老逻辑: 主讲老师按 Course.teacher_id 查 → 必须能查到 (兼容)。"""
    main_id, _, _, course_id = two_teachers_and_course
    with session_scope() as s:
        dao = CourseDao(s)
        rows = dao.find_by_teacher(main_id)
        assert any(c.id == course_id for c in rows), \
            "主讲老师(在 Course.teacher_id 里)查不到自己的课 → W14 之前就坏了"


def test_find_by_teacher_returns_assistant_via_junction(two_teachers_and_course):
    """W14+ 修法核心: 助教老师(只在 course_teacher 关联表里)也能查到自己。

    这条是 P0 回归点 — 没修前会返空 list, 导致
    create_task_dialog 的课程下拉显示 "暂无可选课程"。
    """
    _, assist_id, _, course_id = two_teachers_and_course
    with session_scope() as s:
        dao = CourseDao(s)
        rows = dao.find_by_teacher(assist_id)
        course_ids = {c.id for c in rows}
        assert course_id in course_ids, (
            f"助教老师(teacher_id={assist_id}) 应该在 course_teacher 关联表里查到课"
            f" {course_id}, 实际查到 {course_ids}"
        )


def test_find_by_teacher_excludes_unrelated_teachers(two_teachers_and_course):
    """跟这门课无关的老师 → 不能查到这门课。"""
    _, _, unrelated_id, course_id = two_teachers_and_course
    with session_scope() as s:
        dao = CourseDao(s)
        rows = dao.find_by_teacher(unrelated_id)
        course_ids = {c.id for c in rows}
        assert course_id not in course_ids, "无关老师不应该看到别人的课"


def test_find_by_teacher_dedupes_main_and_assistant():
    """同一门课同时是主讲(在 Course.teacher_id)又是关联表 main 角色 →
    DISTINCT 兜底, 不能返 2 行。
    """
    from src.services.auth_service import AuthService

    teacher = AuthService().register(
        username=_uni("t"), password="123456", real_name="主辅一体测试", role="teacher",
    )
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="主辅一体课",
            course_type="theory",
            teacher_id=teacher.id,
        )
        s.add(course)
        s.flush()
        course_id = course.id
        # 同时进 course_teacher 关联表(模拟"主讲又在关联表里写了一次")
        s.add(CourseTeacher(course_id=course_id, teacher_id=teacher.id, role="main"))
        s.flush()

    try:
        with session_scope() as s:
            dao = CourseDao(s)
            rows = dao.find_by_teacher(teacher.id)
            # 命中 course_id 的行数应该 == 1, 不是 2
            hits = [c for c in rows if c.id == course_id]
            assert len(hits) == 1, f"DISTINCT 漏了, 同课返了 {len(hits)} 行"
    finally:
        with session_scope() as s:
            s.query(CourseTeacher).filter(CourseTeacher.course_id == course_id).delete()
            s.query(Course).filter(Course.id == course_id).delete()
            s.query(UserDao.model).filter(UserDao.model.id == teacher.id).delete()


def test_find_by_teacher_returns_empty_for_nonexistent_teacher():
    """不存在的 teacher_id → 返空 list, 不能爆 SQL 错。"""
    with session_scope() as s:
        dao = CourseDao(s)
        rows = dao.find_by_teacher(99999999)
        assert rows == []
