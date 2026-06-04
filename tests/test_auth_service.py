"""
tests/test_auth_service.py — AuthService 单元测试
- 需要 MySQL 服务可用且 .env 中 DB 配置正确
- 每个测试用独立 username 避免冲突
"""
import os
import uuid

import pytest

from src.services.auth_service import AuthService, AuthError


@pytest.fixture
def auth() -> AuthService:
    return AuthService()


def _uni(prefix: str = "u") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def test_register_and_login_success(auth: AuthService):
    username = _uni("u")
    user = auth.register(
        username=username, password="123456", real_name="测试用户",
        role="student", student_id=_uni("s"), direction="生物医学仪器",
    )
    assert user.id is not None
    assert user.username == username

    # 登录
    logged = auth.login(username, "123456")
    assert logged.id == user.id


def test_register_weak_password_rejected(auth: AuthService):
    with pytest.raises(AuthError, match="密码至少"):
        auth.register(
            username=_uni("u"), password="123", real_name="弱密码",
            role="student", student_id=_uni("s"),
        )


def test_register_invalid_role_rejected(auth: AuthService):
    with pytest.raises(AuthError, match="角色不合法"):
        auth.register(
            username=_uni("u"), password="123456", real_name="非法角色",
            role="admin",  # 非法
        )


def test_register_duplicate_username_rejected(auth: AuthService):
    username = _uni("u")
    auth.register(username=username, password="123456", real_name="A",
                  role="student", student_id=_uni("s"))
    with pytest.raises(AuthError, match="已存在"):
        auth.register(username=username, password="123456", real_name="B",
                      role="student", student_id=_uni("s"))


def test_register_duplicate_student_id_rejected(auth: AuthService):
    sid = _uni("s")
    auth.register(username=_uni("u"), password="123456", real_name="A",
                  role="student", student_id=sid)
    with pytest.raises(AuthError, match="学号"):
        auth.register(username=_uni("u"), password="123456", real_name="B",
                      role="student", student_id=sid)


def test_register_student_must_have_student_id(auth: AuthService):
    with pytest.raises(AuthError, match="学生必须"):
        auth.register(username=_uni("u"), password="123456", real_name="无学号",
                      role="student", student_id=None)


def test_login_wrong_password(auth: AuthService):
    username = _uni("u")
    auth.register(username=username, password="123456", real_name="A",
                  role="student", student_id=_uni("s"))
    with pytest.raises(AuthError, match="用户名或密码错误"):
        auth.login(username, "wrongpass")


def test_login_nonexistent_user(auth: AuthService):
    with pytest.raises(AuthError, match="用户名或密码错误"):
        auth.login("nonexistent_user_xx", "123456")


def test_change_password_success(auth: AuthService):
    username = _uni("u")
    user = auth.register(username=username, password="123456", real_name="A",
                         role="student", student_id=_uni("s"))
    auth.change_password(user.id, "123456", "newpass123")

    # 旧密码失效
    with pytest.raises(AuthError):
        auth.login(username, "123456")
    # 新密码生效
    logged = auth.login(username, "newpass123")
    assert logged.id == user.id


def test_change_password_wrong_old(auth: AuthService):
    username = _uni("u")
    user = auth.register(username=username, password="123456", real_name="A",
                         role="student", student_id=_uni("s"))
    with pytest.raises(AuthError, match="原密码错误"):
        auth.change_password(user.id, "wrongold", "newpass123")
