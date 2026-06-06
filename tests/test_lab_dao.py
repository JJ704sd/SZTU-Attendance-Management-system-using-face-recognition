"""
tests/test_lab_dao.py — 实验室 DAO 单测
"""
import uuid

import pytest

from src.dao.lab_dao import LabDao
from src.db import session_scope
from src.models.course import Laboratory


def _uni(prefix: str = "lab") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_create_and_find():
    with session_scope() as s:
        dao = LabDao(s)
        lab = Laboratory(
            name=_uni("TestLab"),
            location="测试楼",
            safety_level=2,
            required_training="设备",
        )
        s.add(lab)
        s.flush()
        lab_id = lab.id
        # find_by_id
        found = dao.find_by_id(lab_id)
        assert found is not None
        assert found.name.startswith("TestLab_")
        assert found.safety_level == 2
        # 清理
        s.delete(found)
        s.flush()


def test_find_by_safety_level():
    with session_scope() as s:
        dao = LabDao(s)
        # 建 2 个 L3 实验室
        lab_a = Laboratory(name=_uni("L3A"), safety_level=3)
        lab_b = Laboratory(name=_uni("L3B"), safety_level=3)
        s.add_all([lab_a, lab_b])
        s.flush()
        # 查 L3
        rows = dao.find_by_safety_level(3)
        # 至少 2 个（可能有历史测试数据更多）
        lab_a_names = {r.name for r in rows}
        assert any(n.startswith("L3A_") for n in lab_a_names)
        assert any(n.startswith("L3B_") for n in lab_a_names)
        # 清理
        s.delete(lab_a)
        s.delete(lab_b)
        s.flush()


def test_find_all():
    with session_scope() as s:
        dao = LabDao(s)
        # DB 里可能没初始数据（schema.sql 的 INSERT 没人跑过），
        # 这里插入一个再断言 >= 1。
        lab = Laboratory(name=_uni("FA"), safety_level=1)
        s.add(lab)
        s.flush()
        rows = dao.find_all()
        assert any(r.name.startswith("FA_") for r in rows)
        # 清理
        s.delete(lab)
        s.flush()
