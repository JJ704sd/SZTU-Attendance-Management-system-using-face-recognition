"""
models/face.py — 人脸编码表模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, LargeBinary, String, DateTime, SmallInteger, ForeignKey

from src.db import Base


class FaceEncoding(Base):
    __tablename__ = "face_encoding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    encoding = Column(LargeBinary, nullable=False, comment="128维float32向量序列化bytes")
    image_path = Column(String(255), nullable=False)
    is_primary = Column(SmallInteger, default=0)
    created_at = Column(DateTime, default=datetime.now)

    # user = relationship("User", back_populates="face_encodings")

    def to_dict(self) -> dict:
        """debug 辅助；不返回 encoding BLOB（128 维向量序列化后是 512 字节，没必要进 dict）"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "image_path": self.image_path,
            "is_primary": self.is_primary,
            "created_at": self.created_at,
        }

    def __repr__(self):
        return f"<FaceEncoding {self.id} user={self.user_id}>"
