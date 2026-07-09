"""
tests/test_task_signin_code_dao.py — TaskSigninCodeDao 单测

W13+ 引入，签到码（数字 / 二维码）的数据访问层：
  - insert_new: 写一条新码
  - find_active_by_value: 学生签到按 task + type + value 查有效码
  - find_active_by_task_type: 教师端码显示 widget 调
  - deactivate_active_for_task_type: 同任务同类型旧码一刀切失效

风格: 参考 tests/test_lab_dao.py。
清理: 测试结束删除 fixture task + 关联 task_signin_code 行
       （task_signin_code 是 attendance_task 的子表，FK CASCADE 会自动删，
        但教室 / 课程 / 用户靠 fixture 函数显式清）。
"""
import uuid
from datetime import datetime, timedelta

import pytest

from src.dao.task_signin_code_dao import TaskSigninCodeDao
from src.db import session_scope
from src.models.attendance import AttendanceTask
from src.models.course import Course
from src.models.user import User
from src.services.auth_service import AuthService


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def teacher_user():
    """一个 teacher；测试后清理 task / course / user。"""
    user = AuthService().register(
        username=_uni("t"),
        password="123456",
        real_name="签到码DAO测试老师",
        role="teacher",
    )
    yield user
    with session_scope() as s:
        s.query(AttendanceTask).filter(AttendanceTask.teacher_id == user.id).delete()
        s.query(Course).filter(Course.teacher_id == user.id).delete()
        s.query(User).filter(User.id == user.id).delete()


@pytest.fixture
def open_task(teacher_user):
    """一个 status=open 的任务（同时建一个 course 占位 FK）。"""
    with session_scope() as s:
        course = Course(
            course_code=_uni("C"),
            course_name="签到码DAO测试课",
            course_type="theory",
            teacher_id=teacher_user.id,
        )
        s.add(course)
        s.flush()
        course_id = course.id

        task = AttendanceTask(
            course_id=course_id,
            teacher_id=teacher_user.id,
            classroom_id=1,
            start_time=datetime.now() - timedelta(minutes=1),
            end_time=datetime.now() + timedelta(hours=1),
            status="open",
        )
        s.add(task)
        s.flush()
        task_id = task.id

    yield task_id
    # 清理 task_signin_code (FK CASCADE 会自动, 但显式先删保证隔离)
    with session_scope() as s:
        from src.models.task_signin_code import TaskSigninCode
        s.query(TaskSigninCode).filter(TaskSigninCode.task_id == task_id).delete()
        s.query(AttendanceTask).filter(AttendanceTask.id == task_id).delete()
        s.query(Course).filter(Course.id == course_id).delete()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_insert_new_and_get(open_task):
    """insert + 通过 find_active_by_value 拿到。"""
    task_id = open_task
    expires = datetime.now() + timedelta(seconds=60)
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        new_code = dao.insert_new(
            task_id=task_id,
            code_type="digit",
            code_value="1234",
            expires_at=expires,
        )
        s.flush()
        code_id = new_code.id
        assert new_code.is_active == 1
        assert new_code.code_value == "1234"

    # 在新 session 里查
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        found = dao.find_active_by_value(task_id, "digit", "1234")
        assert found is not None
        assert found.id == code_id
        assert found.code_type == "digit"
        assert found.code_value == "1234"


def test_find_active_by_value_filters_expired(open_task):
    """expires_at < now → find_active_by_value 返 None。"""
    task_id = open_task
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        # expires_at = 1 小时前
        dao.insert_new(
            task_id=task_id,
            code_type="digit",
            code_value="0001",
            expires_at=datetime.now() - timedelta(hours=1),
        )
        s.flush()

    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        found = dao.find_active_by_value(task_id, "digit", "0001")
        assert found is None, "过期码应被过滤"


def test_find_active_by_value_filters_inactive(open_task):
    """is_active=0 → find_active_by_value 返 None。"""
    task_id = open_task
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        new_code = dao.insert_new(
            task_id=task_id,
            code_type="digit",
            code_value="0002",
            expires_at=datetime.now() + timedelta(seconds=60),
        )
        s.flush()
        new_code.is_active = 0
        s.flush()

    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        found = dao.find_active_by_value(task_id, "digit", "0002")
        assert found is None, "is_active=0 应被过滤"


def test_find_active_by_value_filters_wrong_value(open_task):
    """code_value 不匹配 → None。"""
    task_id = open_task
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        dao.insert_new(
            task_id=task_id,
            code_type="digit",
            code_value="0003",
            expires_at=datetime.now() + timedelta(seconds=60),
        )
        s.flush()

    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        # 别的码查不到
        found = dao.find_active_by_value(task_id, "digit", "9999")
        assert found is None


def test_find_active_by_value_combo_filter_all_conditions(open_task):
    """R16: 多条件组合过滤 — find_active_by_value 同时校验 5 个条件。

    已有测试各自覆盖单个条件 (filters_wrong_value / filters_expired /
    filters_inactive / insert_new_and_get), 但没测「组合」:
    - 同 task 多个 type, 查其中一个 type 应只返该 type
    - 同 type 多值, 查一个应只返该值
    - 同 value 但 expired, 应返 None (即便其他条件对)
    - 同 value 但 wrong task, 应返 None

    这是学生端签到校验的核心多条件 SQL — 任何一条 false 应返 None,
    防止「value 撞对但任务错」导致错签别的 task.
    """
    task_id = open_task
    now = datetime.now()
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        # 写入一组: 1 个 active digit + 1 个 active qr + 1 个 expired digit
        c_active_digit = dao.insert_new(task_id, "digit", "5555", now + timedelta(minutes=5))
        c_active_qr = dao.insert_new(task_id, "qr", "tok_qq_xx", now + timedelta(minutes=5))
        c_expired_digit = dao.insert_new(task_id, "digit", "6666", now - timedelta(seconds=1))
        s.flush()
        active_digit_id = c_active_digit.id
        active_qr_id = c_active_qr.id

    with session_scope() as s:
        dao = TaskSigninCodeDao(s)

        # 1) 全条件匹配 → 返 digit active
        found = dao.find_active_by_value(task_id, "digit", "5555")
        assert found is not None and found.id == active_digit_id

        # 2) code_type 不匹配 (digit 查 qr value) → None
        # 同 task + value 'tok_qq_xx' 但 type='digit' → 查不到
        assert dao.find_active_by_value(task_id, "digit", "tok_qq_xx") is None

        # 3) 全条件匹配 → 返 qr active
        found_qr = dao.find_active_by_value(task_id, "qr", "tok_qq_xx")
        assert found_qr is not None and found_qr.id == active_qr_id

        # 4) value 撞但 expired → None (即 '6666' 存在 DB 里但因过期不命中)
        assert dao.find_active_by_value(task_id, "digit", "6666") is None

        # 5) value 撞但 task_id 错 → None (防「value 撞上但任务错」签别人 task)
        wrong_task_id = task_id + 999_999
        assert dao.find_active_by_value(wrong_task_id, "digit", "5555") is None


def test_deactivate_active_for_task_type(open_task):
    """同任务同类型插 2 条，deactivate 一刀切返回 2，全部 is_active=0。"""
    task_id = open_task
    expires = datetime.now() + timedelta(seconds=60)
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        c1 = dao.insert_new(task_id, "digit", "1000", expires)
        c2 = dao.insert_new(task_id, "digit", "2000", expires)
        s.flush()
        c1_id, c2_id = c1.id, c2.id

        # 调用 deactivate
        n = dao.deactivate_active_for_task_type(task_id, "digit")
        assert n == 2, f"应失效 2 条，实际 {n}"

        # 验证 is_active 全部 0
        s.refresh(c1)
        s.refresh(c2)
        assert c1.is_active == 0
        assert c2.is_active == 0


def test_find_active_by_task_type_returns_active_only(open_task):
    """多类型 + 多个，过滤正确：digit 只返 digit 且 active 的；qr 同理。"""
    task_id = open_task
    now = datetime.now()
    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        # digit: 1 active + 1 expired + 1 inactive
        dao.insert_new(task_id, "digit", "3000", now + timedelta(seconds=60))
        dao.insert_new(task_id, "digit", "3001", now - timedelta(seconds=1))  # expired
        c_inactive = dao.insert_new(
            task_id, "digit", "3002", now + timedelta(seconds=60)
        )
        c_inactive.is_active = 0
        # qr: 2 active
        dao.insert_new(task_id, "qr", "tok_aaaa", now + timedelta(seconds=60))
        dao.insert_new(task_id, "qr", "tok_bbbb", now + timedelta(seconds=60))
        # 别的 type 不该混进来
        s.flush()

    with session_scope() as s:
        dao = TaskSigninCodeDao(s)
        digit_codes = dao.find_active_by_task_type(task_id, "digit")
        qr_codes = dao.find_active_by_task_type(task_id, "qr")

        # digit 只应 1 条
        assert len(digit_codes) == 1, f"digit 应只返 1 条 active，实际 {len(digit_codes)}"
        assert digit_codes[0].code_value == "3000"
        # qr 2 条
        assert len(qr_codes) == 2
        qr_values = {c.code_value for c in qr_codes}
        assert qr_values == {"tok_aaaa", "tok_bbbb"}
        # 全部 is_active=1
        for c in digit_codes + qr_codes:
            assert c.is_active == 1
            assert c.expires_at > now
