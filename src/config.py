"""
config.py — 全局配置
从 .env 读取数据库连接等敏感信息，提供统一访问入口。
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env（项目根目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Config:
    """全局配置单例"""

    # 数据库
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "attendance_lab")

    @classmethod
    def database_url(cls) -> str:
        """SQLAlchemy 风格的 MySQL URL"""
        return (
            f"mysql+pymysql://{cls.DB_USER}:{cls.DB_PASSWORD}"
            f"@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}?charset=utf8mb4"
        )

    # 人脸识别
    FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.45"))
    FACE_SAMPLE_COUNT = int(os.getenv("FACE_SAMPLE_COUNT", "30"))
    DATASET_DIR = PROJECT_ROOT / "dataset" / "face_images"

    # 安全
    LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))

    # 路径
    ASSETS_DIR = PROJECT_ROOT / "src" / "assets"
    PROJECT_ROOT = PROJECT_ROOT


# 快速自检
if __name__ == "__main__":
    cfg = Config()
    print("DB URL:", cfg.database_url().replace(cfg.DB_PASSWORD, "***"))
    print("Project root:", cfg.PROJECT_ROOT)
    print("Dataset dir:", cfg.DATASET_DIR)
