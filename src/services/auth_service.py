"""
services/auth_service.py — 认证服务
- 注册：用户名唯一、密码 bcrypt、role 校验
- 登录：bcrypt 校验、返回 User 对象
- 退出：清空 session（在 UI 层做）
"""
from typing import Optional, Tuple
import re

from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.user import User
from src.utils.crypto import hash_password, verify_password
from src.config import Config

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,50}$")


class AuthError(Exception):
    """认证相关错误"""


class AuthService:
    def __init__(self, dao: UserDao = None):
        # 允许注入 dao，便于测试
        self._dao = dao

    @property
    def dao(self) -> UserDao:
        if self._dao is None:
            # 默认从 session_scope 取
            # 实际每次新建一个 session 即可（轻量）
            from src.db import SessionLocal
            return UserDao(SessionLocal())
        return self._dao

    # -----------------------------------------------------
    # 注册
    # -----------------------------------------------------
    def register(self, username: str, password: str, real_name: str, role: str,
                 student_id: str = None, direction: str = None,
                 email: str = None, phone: str = None) -> User:
        """
        注册新用户。
        抛出 AuthError 表示业务错误。
        """
        # 入参校验
        if not USERNAME_RE.match(username):
            raise AuthError("用户名必须是 3-50 位字母/数字/下划线")
        if len(password) < 6:
            raise AuthError("密码至少 6 位")
        if role not in ("student", "teacher", "lab_admin"):
            raise AuthError("角色不合法")
        if role == "student" and not student_id:
            raise AuthError("学生必须填写学号")

        with session_scope() as s:
            dao = UserDao(s)
            if dao.find_by_username(username):
                raise AuthError(f"用户名 {username} 已存在")
            if student_id and dao.find_by_student_id(student_id):
                raise AuthError(f"学号 {student_id} 已被注册")

            user = User(
                username=username,
                password_hash=hash_password(password),
                real_name=real_name,
                role=role,
                student_id=student_id,
                direction=direction,
                email=email,
                phone=phone,
                is_active=1,
            )
            s.add(user)
            s.flush()
            s.refresh(user)
            # session_scope 退出时自动 commit
            s.expunge(user)  # 让 user 在 session 关闭后仍可访问属性
            return user

    # -----------------------------------------------------
    # 登录
    # -----------------------------------------------------
    def login(self, username: str, password: str) -> User:
        """成功返回 User，失败抛 AuthError"""
        with session_scope() as s:
            dao = UserDao(s)
            user = dao.find_by_username(username)
            if not user:
                raise AuthError("用户名或密码错误")
            if user.is_active != 1:
                raise AuthError("账号已被禁用")
            if not verify_password(password, user.password_hash):
                raise AuthError("用户名或密码错误")
            s.expunge(user)
            return user

    # -----------------------------------------------------
    # 修改密码
    # -----------------------------------------------------
    def change_password(self, user_id: int, old_pwd: str, new_pwd: str) -> bool:
        with session_scope() as s:
            dao = UserDao(s)
            user = dao.get(user_id)
            if not user:
                raise AuthError("用户不存在")
            if not verify_password(old_pwd, user.password_hash):
                raise AuthError("原密码错误")
            if len(new_pwd) < 6:
                raise AuthError("新密码至少 6 位")
            dao.update_password(user, hash_password(new_pwd))
            return True
