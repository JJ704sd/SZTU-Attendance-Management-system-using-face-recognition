"""
dao/face_dao.py — 人脸编码 DAO
"""
from typing import List

from src.dao.base import BaseDao
from src.models.face import FaceEncoding


class FaceEncodingDao(BaseDao[FaceEncoding]):
    model = FaceEncoding

    def find_by_user(self, user_id: int) -> List[FaceEncoding]:
        return self.s.query(FaceEncoding).filter(
            FaceEncoding.user_id == user_id
        ).order_by(FaceEncoding.id).all()

    def delete_by_user(self, user_id: int) -> int:
        rows = self.s.query(FaceEncoding).filter(
            FaceEncoding.user_id == user_id
        ).all()
        n = len(rows)
        for r in rows:
            self.s.delete(r)
        self.s.flush()
        return n

    def set_primary(self, encoding_id: int, user_id: int) -> None:
        # 先把同用户其他行的 is_primary 置 0
        self.s.query(FaceEncoding).filter(
            FaceEncoding.user_id == user_id,
            FaceEncoding.id != encoding_id,
        ).update({FaceEncoding.is_primary: 0})
        # 再设本行为 1
        self.s.query(FaceEncoding).filter(
            FaceEncoding.id == encoding_id
        ).update({FaceEncoding.is_primary: 1})
        self.s.flush()
