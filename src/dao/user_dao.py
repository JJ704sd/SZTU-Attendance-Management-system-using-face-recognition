"""
dao/user_dao.py — 用户 DAO
"""
from typing import Optional
from sqlalchemy.orm import Session

from src.dao.base import BaseDao
from src.models.user import User


class UserDao(BaseDao[User]):
    model = User

    def find_by_username(self, username: str) -> Optional[User]:
        return self.s.query(User).filter(User.username == username).first()

    def find_by_student_id(self, student_id: str) -> Optional[User]:
        return self.s.query(User).filter(User.student_id == student_id).first()

    def find_by_role(self, role: str):
        return self.s.query(User).filter(User.role == role).all()

    def update_password(self, user: User, new_hash: str):
        user.password_hash = new_hash
        self.s.flush()
