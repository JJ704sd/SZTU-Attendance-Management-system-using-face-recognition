"""
tests/test_lab_access_service.py — LabAccessService.check_access 单测

W4 Phase 3c 验收:
- 3 个通过分支（教师/管理员/有效培训学生）
- 4 个拒绝分支（无培训/过期/类型不匹配/高等级分数不够）
"""
import uuid
from datetime import date, timedelta

import pytest

from src.dao.lab_access_log_dao import LabAccessLogDao
from src.dao.lab_dao import LabDao
from src.dao.lab_training_dao import LabTrainingDao
from src.db import session_scope
from src.models.course import Laboratory
from src.models.lab import LabAccessLog, LabTraining
from src.models.user import User
from src.services.auth_service import AuthService
from src.services.lab_access_service import LabAccessService


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def teacher_user():
    """教师账号（用于通过分支测试）"""
    user = AuthService().register(
        username=_uni("t"), password="123456", real_name="准入测试老师",
        role="teacher",
    )
    yield user
    with session_scope() as s:
        s.query(LabAccessLog).filter(LabAccessLog.student_id == user.id).delete()
        s.query(LabTraining).filter(LabTraining.student_id == user.id).delete()
        s.query(User).filter(User.id == user.id).delete()


@pytest.fixture
def student_user():
    """学生账号"""
    user = AuthService().register(
        username=_uni("s"), password="123456", real_name="准入测试学生",
        role="student", student_id=_uni("sid"),
    )
    yield user
    with session_scope() as s:
        s.query(LabAccessLog).filter(LabAccessLog.student_id == user.id).delete()
        s.query(LabTraining).filter(LabTraining.student_id == user.id).delete()
        s.query(User).filter(User.id == user.id).delete()


def _create_lab(name, safety_level, required_training):
    with session_scope() as s:
        lab = Laboratory(
            name=name, safety_level=safety_level,
            required_training=required_training,
        )
        s.add(lab)
        s.flush()
        return lab.id


def _create_training(student_id, lab_id, training_type, days_to_expiry, score):
    """建一条培训记录。days_to_expiry 负数=已过期。"""
    today = date.today()
    with session_scope() as s:
        row = LabTraining(
            student_id=student_id,
            lab_id=lab_id,
            training_type=training_type,
            completion_date=today - timedelta(days=10),
            expiry_date=today + timedelta(days=days_to_expiry),
            score=score,
        )
        s.add(row)
        s.flush()
        return row.id


def _cleanup_lab(lab_id):
    with session_scope() as s:
        s.query(LabAccessLog).filter(LabAccessLog.lab_id == lab_id).delete()
        s.query(LabTraining).filter(LabTraining.lab_id == lab_id).delete()
        s.query(Laboratory).filter(Laboratory.id == lab_id).delete()


# ====================================================
# 通过分支（3 个）
# ====================================================
def test_check_access_teacher_passes(teacher_user):
    """教师直接放行（不管实验室等级/培训）"""
    lab_id = _create_lab(_uni("L"), safety_level=5, required_training="化学")
    try:
        service = LabAccessService()
        result = service.check_access(teacher_user.id, lab_id)
        assert result.granted is True
        assert "teacher" in result.reason or "非学生" in result.reason
    finally:
        _cleanup_lab(lab_id)


def test_check_access_student_with_valid_training_passes(student_user):
    """学生有有效培训（未过期 + 类型匹配 + 分数够）→ 放行"""
    lab_id = _create_lab(_uni("L"), safety_level=2, required_training="设备")
    try:
        _create_training(
            student_user.id, lab_id,
            training_type="设备", days_to_expiry=80, score=85.0,
        )
        service = LabAccessService()
        result = service.check_access(student_user.id, lab_id)
        assert result.granted is True
        assert "通过" in result.reason
    finally:
        _cleanup_lab(lab_id)


def test_check_access_lab_admin_passes(teacher_user):
    """实验室管理员也走"非学生"分支放行"""
    # 改 fixture 的 teacher_user role 为 lab_admin
    with session_scope() as s:
        u = s.get(User, teacher_user.id)
        u.role = "lab_admin"
    try:
        lab_id = _create_lab(_uni("L"), safety_level=5, required_training="化学")
        try:
            service = LabAccessService()
            result = service.check_access(teacher_user.id, lab_id)
            assert result.granted is True
            assert "lab_admin" in result.reason
        finally:
            _cleanup_lab(lab_id)
    finally:
        # 恢复 role（fixture 清理时删 user，role 无所谓）
        pass


# ====================================================
# 拒绝分支（4 个）
# ====================================================
def test_check_access_student_no_training_rejected(student_user):
    """学生无任何培训记录 → 拒绝"""
    lab_id = _create_lab(_uni("L"), safety_level=2, required_training="设备")
    try:
        service = LabAccessService()
        result = service.check_access(student_user.id, lab_id)
        assert result.granted is False
        assert "未完成" in result.reason
    finally:
        _cleanup_lab(lab_id)


def test_check_access_student_expired_training_rejected(student_user):
    """学生培训过期 → 拒绝"""
    lab_id = _create_lab(_uni("L"), safety_level=2, required_training="设备")
    try:
        _create_training(
            student_user.id, lab_id,
            training_type="设备", days_to_expiry=-10, score=85.0,  # 过期 10 天
        )
        service = LabAccessService()
        result = service.check_access(student_user.id, lab_id)
        assert result.granted is False
        assert "过期" in result.reason
    finally:
        _cleanup_lab(lab_id)


def test_check_access_student_wrong_training_type_rejected(student_user):
    """学生培训类型不匹配 → 拒绝"""
    lab_id = _create_lab(_uni("L"), safety_level=2, required_training="生物")
    try:
        _create_training(
            student_user.id, lab_id,
            training_type="设备",  # 持"设备"但实验室要"生物"
            days_to_expiry=80, score=85.0,
        )
        service = LabAccessService()
        result = service.check_access(student_user.id, lab_id)
        assert result.granted is False
        assert "培训类型" in result.reason
    finally:
        _cleanup_lab(lab_id)


def test_check_access_high_level_low_score_rejected(student_user):
    """高等级实验室（safety_level=4/5）+ score<90 → 拒绝"""
    lab_id = _create_lab(_uni("L"), safety_level=5, required_training="辐射")
    try:
        _create_training(
            student_user.id, lab_id,
            training_type="辐射", days_to_expiry=80, score=85.0,  # 分数 85 < 90
        )
        service = LabAccessService()
        result = service.check_access(student_user.id, lab_id)
        assert result.granted is False
        assert "≥90" in result.reason or "分数" in result.reason
    finally:
        _cleanup_lab(lab_id)


# ====================================================
# 边界 + 集成
# ====================================================
def test_check_access_high_level_high_score_passes(student_user):
    """safety_level=5 + score=95 → 通过（边界：刚好高于 90）"""
    lab_id = _create_lab(_uni("L"), safety_level=5, required_training="辐射")
    try:
        _create_training(
            student_user.id, lab_id,
            training_type="辐射", days_to_expiry=80, score=95.0,
        )
        service = LabAccessService()
        result = service.check_access(student_user.id, lab_id)
        assert result.granted is True
    finally:
        _cleanup_lab(lab_id)


def test_check_access_writes_log(student_user):
    """每次 check_access 都应该写 lab_access_log"""
    lab_id = _create_lab(_uni("L"), safety_level=2, required_training="设备")
    try:
        service = LabAccessService()
        service.check_access(student_user.id, lab_id)  # 失败（无培训）
        with session_scope() as s:
            logs = LabAccessLogDao(s).find_by_lab(lab_id, limit=10)
        assert len(logs) == 1
        assert logs[0].granted == 0
        assert "未完成" in logs[0].reason
    finally:
        _cleanup_lab(lab_id)
