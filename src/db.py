"""
db.py — SQLAlchemy 引擎、Session、Base
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from contextlib import contextmanager

from src.config import Config

# echo=False 关掉 SQL 日志；pool_pre_ping 处理 MySQL 长时间空闲断连
engine = create_engine(
    Config.database_url(),
    echo=False,
    pool_pre_ping=True,
    pool_recycle=3600,
    # W5 调试: 临时开 echo 看 create_all 跑到哪
    # echo=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


@contextmanager
def session_scope() -> Session:
    """上下文管理器形式的 session，自动 commit/rollback"""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    """建表（开发用，生产请用 alembic）"""
    import logging
    log = logging.getLogger(__name__)
    log.info("init_db: 开始导入 models")
    # 导入所有模型，确保 Base.metadata 知道它们
    from src.models import (
        user, face, course, attendance, lab,
        course_enrollment, login_attempt,  # W4 Phase 1
    )  # noqa
    log.info("init_db: models 导入完成, 调 create_all")
    try:
        Base.metadata.create_all(engine)
        log.info("init_db: create_all 完成")
    except Exception as e:
        log.error("init_db: create_all 抛异常: %s", e)
        raise


if __name__ == "__main__":
    print("Initializing database...")
    init_db()
    print("Done.")
