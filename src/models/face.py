"""
models/face.py — 人脸编码表模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, LargeBinary, String, DateTime, SmallInteger, ForeignKey
from sqlalchemy.orm import relationship

from src.db import Base


class FaceEncoding(Base):
    __tablename__ = "face_encoding"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    encoding = Column(LargeBinary, nullable=False, comment="128维float32向量bytes")
    image_path = Column(String(255), nullable=False)
    is_primary = Column(SmallInteger, default=0)
    created_at = Column(DateTime, default=datetime.now)

    # user = relationship("User", back_populates="face_encodings")

    def __repr__(self):
        return f"<FaceEncoding {self.id} user={self.user_id}>"
