"""
dao/base.py — DAO 基类，封装通用 CRUD
"""
from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session

from src.db import Base

T = TypeVar("T", bound=Base)


class BaseDao(Generic[T]):
    model: Type[T] = None  # 子类必须指定

    def __init__(self, session: Session):
        self.s = session

    def get(self, pk) -> Optional[T]:
        return self.s.query(self.model).get(pk)

    def get_all(self) -> List[T]:
        return self.s.query(self.model).all()

    def add(self, obj: T) -> T:
        self.s.add(obj)
        self.s.flush()
        return obj

    def add_all(self, objs: List[T]):
        self.s.add_all(objs)
        self.s.flush()

    def delete(self, obj: T):
        self.s.delete(obj)

    def commit(self):
        self.s.commit()

    def rollback(self):
        self.s.rollback()
