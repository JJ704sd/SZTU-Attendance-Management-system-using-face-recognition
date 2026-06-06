"""
tests/test_lab_training_dao.py — 安全培训 DAO 单测
"""
import uuid
from datetime import date, timedelta

import pytest

from src.dao.lab_dao import LabDao
from src.dao.lab_training_dao import LabTrainingDao
from src.db import session_scope
from src.models.course import Laboratory
from src.models.lab import LabTraining
from src.services.auth_service import AuthService


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def student_and_lab():
    """注册一个临时学生 + 建一个临时实验室，测试后清理。"""
    user = AuthService().register(
        username=_uni("s"),
        password="123456",
        real_name="培训测试",
        role="student",
        student_id=_uni("sid"),
    )
    with session_scope() as s:
        lab = Laboratory(name=_uni("TL"), safety_level=2, required_training="设备")
        s.add(lab)
        s.flush()
        lab_id = lab.id
    yield user.id, lab_id
    # 清理
    with session_scope() as s:
        s.query(LabTraining).filter(LabTraining.student_id == user.id).delete()
        s.query(Laboratory).filter(Laboratory.id == lab_id).delete()


def test_add_and_find_valid(student_and_lab):
    student_id, lab_id = student_and_lab
    today = date.today()
    with session_scope() as s:
        dao = LabTrainingDao(s)
        row = LabTraining(
            student_id=student_id,
            lab_id=lab_id,
            training_type="设备",
            completion_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=80),
            score=85.0,
        )
        s.add(row)
        s.flush()
        # find_valid 应该返回这条
        valid = dao.find_valid_by_student_lab(student_id, lab_id, today)
        assert valid is not None
        assert valid.score == 85.0
        assert valid.training_type == "设备"


def test_find_valid_skips_expired(student_and_lab):
    student_id, lab_id = student_and_lab
    today = date.today()
    with session_scope() as s:
        dao = LabTrainingDao(s)
        # 过期 10 天
        expired = LabTraining(
            student_id=student_id,
            lab_id=lab_id,
            training_type="设备",
            completion_date=today - timedelta(days=200),
            expiry_date=today - timedelta(days=10),
            score=85.0,
        )
        s.add(expired)
        s.flush()
        # find_valid 不应返回过期
        valid = dao.find_valid_by_student_lab(student_id, lab_id, today)
        assert valid is None


def test_find_by_student(student_and_lab):
    student_id, lab_id = student_and_lab
    today = date.today()
    with session_scope() as s:
        dao = LabTrainingDao(s)
        for i in range(3):
            s.add(LabTraining(
                student_id=student_id, lab_id=lab_id,
                training_type="设备",
                completion_date=today - timedelta(days=10),
                expiry_date=today + timedelta(days=80 + i),
                score=85.0,
            ))
        s.flush()
        rows = dao.find_by_student(student_id)
        assert len(rows) == 3
