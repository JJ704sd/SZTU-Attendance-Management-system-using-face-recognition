"""
services/auth_service.py — 认证服务
- 注册：用户名唯一、密码 bcrypt、role 校验
- 登录：bcrypt 校验、返回 User 对象；W4 加 LOGIN_MAX_ATTEMPTS 防暴力破解
- 退出：清空 session（在 UI 层做）
"""
import re

from src.config import Config
from src.constants import ROLE_STUDENT, VALID_ROLES
from src.dao.login_attempt_dao import LoginAttemptDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.user import User
from src.utils.crypto import hash_password, verify_password

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,50}$")


class AuthError(Exception):
    """认证相关错误"""


class AuthService:
    def __init__(self):
        # 所有方法内部用 session_scope() 自管 session，不需要外部注入
        pass

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
        if role not in VALID_ROLES:
            raise AuthError("角色不合法")
        if role == ROLE_STUDENT and not student_id:
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
        """成功返回 User，失败抛 AuthError。

        W4 Phase 3a: 加 LOGIN_MAX_ATTEMPTS 防暴力破解。
        流程:
        1. 查最近 LOGIN_MAX_ATTEMPTS 次失败次数
        2. >= 阈值 → 直接抛 AuthError("账号已锁定")
        3. 校验密码
        4. 成功 → record_attempt(success=True) + 返回
        5. 失败 → record_attempt(success=False) + 抛 AuthError

        ⚠️ 关键: 失败分支在 raise 之前必须显式 s.commit()，否则 session_scope
        退出时的 rollback 会把 record_attempt 一起回滚，导致锁定永远不触发。
        """
        with session_scope() as s:
            attempt_dao = LoginAttemptDao(s)
            # 1. 检查是否已锁定
            recent_failures = attempt_dao.count_recent_failures(
                username, limit=Config.LOGIN_MAX_ATTEMPTS,
            )
            if recent_failures >= Config.LOGIN_MAX_ATTEMPTS:
                raise AuthError(
                    f"账号已锁定：连续 {Config.LOGIN_MAX_ATTEMPTS} 次登录失败，"
                    f"请联系管理员解锁"
                )

            # 2-3. 校验密码
            user_dao = UserDao(s)
            user = user_dao.find_by_username(username)
            if not user:
                attempt_dao.record_attempt(username, success=False)
                s.commit()  # 显式提交，避免 raise 触发 rollback 抹掉记录
                raise AuthError("用户名或密码错误")
            if user.is_active != 1:
                # 禁用账号不记录为"失败"（避免永久锁定），但仍抛错
                raise AuthError("账号已被禁用")
            if not verify_password(password, user.password_hash):
                attempt_dao.record_attempt(username, success=False)
                s.commit()  # 同上
                raise AuthError("用户名或密码错误")

            # 4. 成功
            attempt_dao.record_attempt(username, success=True)
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
