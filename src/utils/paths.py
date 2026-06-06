"""
utils/paths.py — 全局路径 helper

W5 新增：统一处理 dev / PyInstaller 两种环境的 APP 根目录。
- dev 环境 (python -m src.main):  APP_ROOT = 项目根
- PyInstaller 打包后 (双击 exe):  APP_ROOT = exe 所在目录

所有资源路径 (models/、dataset/、.env) 都基于 APP_ROOT。
"""
import sys
from pathlib import Path


def get_app_root() -> Path:
    """返回应用根目录绝对路径。

    判定:
    - sys.frozen=True  → PyInstaller 打包后 → sys.executable 所在目录
    - 否则             → dev 模式 → src/utils/paths.py 往上级到项目根
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


# 单例：所有引用方共享同一个路径
APP_ROOT: Path = get_app_root()
MODELS_DIR: Path = APP_ROOT / "models"
# 注意: 人脸采集图片路径走 src.config.Config.DATASET_DIR
# (APP_ROOT / "dataset" / "face_images"), 不在这里重复定义, 避免不一致。
