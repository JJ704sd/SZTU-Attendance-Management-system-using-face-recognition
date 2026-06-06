"""
tests/test_login_attempt_dao.py — 登录尝试 DAO 单测
"""
import uuid

import pytest

from src.dao.login_attempt_dao import LoginAttemptDao
from src.db import session_scope


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_record_and_count_failures():
    username = _uni("attempt")
    with session_scope() as s:
        dao = LoginAttemptDao(s)
        dao.record_attempt(username, success=False)
        dao.record_attempt(username, success=False)
        dao.record_attempt(username, success=True)
        # 3 次尝试，2 次失败（按 id 倒序）
        assert dao.count_recent_failures(username, limit=10) == 2
        # limit=2 返回最近 2 次（1 成功 + 1 失败 → 1 失败）
        assert dao.count_recent_failures(username, limit=2) == 1
        # 清理
        dao.clear_attempts(username)


def test_count_recent_failures_empty():
    """新用户没记录应返回 0。"""
    with session_scope() as s:
        dao = LoginAttemptDao(s)
        n = dao.count_recent_failures("never_existed_user_xyz", limit=5)
    assert n == 0


def test_last_attempt():
    username = _uni("last")
    with session_scope() as s:
        dao = LoginAttemptDao(s)
        dao.record_attempt(username, success=False)
        dao.record_attempt(username, success=True)
        last = dao.last_attempt(username)
        assert last is not None
        assert last.success == 1
        # 清理
        dao.clear_attempts(username)


def test_clear_attempts():
    username = _uni("clear")
    with session_scope() as s:
        dao = LoginAttemptDao(s)
        for _ in range(3):
            dao.record_attempt(username, success=False)
        n = dao.clear_attempts(username)
        assert n == 3
        # 再查应为空
        assert dao.count_recent_failures(username) == 0

