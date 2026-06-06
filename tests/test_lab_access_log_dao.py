"""
tests/test_lab_access_log_dao.py — 实验室准入日志 DAO 单测
"""
import uuid

import pytest

from src.dao.lab_access_log_dao import LabAccessLogDao
from src.dao.lab_dao import LabDao
from src.db import session_scope
from src.models.course import Laboratory
from src.models.lab import LabAccessLog
from src.services.auth_service import AuthService


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def student_and_lab():
    user = AuthService().register(
        username=_uni("s"),
        password="123456",
        real_name="准入测试",
        role="student",
        student_id=_uni("sid"),
    )
    with session_scope() as s:
        lab = Laboratory(name=_uni("AL"), safety_level=2, required_training="设备")
        s.add(lab)
        s.flush()
        lab_id = lab.id
    yield user.id, lab_id
    # 清理
    with session_scope() as s:
        s.query(LabAccessLog).filter(LabAccessLog.student_id == user.id).delete()
        s.query(Laboratory).filter(Laboratory.id == lab_id).delete()


def test_log_and_find_by_lab(student_and_lab):
    student_id, lab_id = student_and_lab
    with session_scope() as s:
        dao = LabAccessLogDao(s)
        dao.log_attempt(lab_id=lab_id, granted=True, student_id=student_id, reason="OK")
        dao.log_attempt(lab_id=lab_id, granted=False, student_id=student_id, reason="培训过期")
        rows = dao.find_by_lab(lab_id, limit=10)
        assert len(rows) == 2
        # 最近 1 条应该是"培训过期"
        assert rows[0].granted == 0
        assert "过期" in rows[0].reason


def test_count_recent_grants(student_and_lab):
    student_id, lab_id = student_and_lab
    with session_scope() as s:
        dao = LabAccessLogDao(s)
        for _ in range(3):
            dao.log_attempt(lab_id=lab_id, granted=True, student_id=student_id)
        dao.log_attempt(lab_id=lab_id, granted=False, student_id=student_id, reason="拒绝")
        # 60 分钟内 3 次放行 + 1 次拒绝
        n = dao.count_recent_grants(lab_id, since_minutes=60)
        assert n == 3
