"""
dao/base.py — DAO 基类，封装通用 CRUD

R16 清理: 删孤儿方法 commit/rollback。
  原因: 全代码库 (services + scripts) 都用 session_scope() 自动
  commit/rollback, 没人调 dao.commit()/rollback()。保留只会误导
  后人以为 DAO 自管事务, 实际调用方应全程依赖 session_scope 上下文。
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
        # SQLAlchemy 2.0: Session.get(model, pk) 替代 self.s.query(model).get(pk)
        return self.s.get(self.model, pk)

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
