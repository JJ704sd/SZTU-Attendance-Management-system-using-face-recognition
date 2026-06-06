"""
main.py — 应用入口
启动方式：在项目根目录运行 `python -m src.main`
"""
import sys
import logging
from pathlib import Path

# 把项目根目录加入 sys.path，兼容 `python src/main.py` 这种直接执行方式
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from PyQt5.QtWidgets import QApplication, QMessageBox

from src.db import init_db
from src.ui.login_window import LoginWindow
from src.ui.styles import apply_global_style
from src.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def main():
    # 1. 初始化数据库（建表）
    try:
        init_db()
        log.info("数据库初始化完成")
    except Exception as e:
        QMessageBox.critical(
            None, "数据库错误",
            f"无法连接或初始化数据库：\n{e}\n\n"
            f"请检查 .env 中的 DB_PASSWORD 是否正确，以及 MySQL 服务是否启动。\n"
            f"当前配置: {Config.database_url().replace(Config.DB_PASSWORD, '***')}"
        )
        sys.exit(1)

    # 1.5. 人脸编码缓存预热（避免首次识别冷启动拉全表）
    # 失败不挂：缓存空只是首次识别慢一点，登录/UI 都不受影响。
    try:
        from src.services.face_service import _FaceCache
        _FaceCache.get().refresh()
        n_users = len(_FaceCache.get().all())
        log.info(f"人脸编码缓存预热完成：{n_users} 个用户")
    except Exception as e:
        log.warning(f"人脸编码缓存预热失败：{e}（首次识别时会冷启动）")

    # 2. 启动 Qt
    app = QApplication(sys.argv)
    app.setApplicationName("智能考勤与实验室准入系统")
    app.setStyle("Fusion")
    apply_global_style(app)

    # 3. 登录窗口
    login = LoginWindow()
    login.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
