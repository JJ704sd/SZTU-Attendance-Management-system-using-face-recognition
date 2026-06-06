"""
main.py — 应用入口
启动方式：在项目根目录运行 `python -m src.main`

W5 改动: 启动时把日志同时写 APP_ROOT/app.log，
方便打包后 (runw.exe 吞 stderr) 还能看启动状态。
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

# 走 src.utils.paths 单例（PyInstaller 兼容）
from src.utils.paths import APP_ROOT

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)


def _setup_file_logging():
    """W5: 同时写日志到 APP_ROOT/app.log
    (dev: 项目根；打包后: exe 同级)。
    移到 main() 体内，确保 main() 真正开始跑时再配。
    """
    try:
        _log_path = APP_ROOT / "app.log"
        _fh = logging.FileHandler(_log_path, mode="a", encoding="utf-8")
        _fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logging.getLogger().addHandler(_fh)
        log.info("W5: 文件日志已启用 -> %s", _log_path)
    except Exception as e:
        log.warning("W5: 文件日志启用失败: %s", e)


def main():
    _setup_file_logging()
    log.info("=== 应用启动 ===")

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

    # 1.6. dlib 模型预热（验证 PyInstaller 打包后 models/ 路径可访问）
    # 失败不挂：首次刷脸时还会 _load_models() 重试。
    try:
        from src.utils.face_helper import ensure_models
        sp_path, fr_path = ensure_models()
        log.info(
            f"dlib 模型路径 OK: sp={sp_path.name} ({sp_path.stat().st_size//1024//1024}MB), "
            f"fr={fr_path.name} ({fr_path.stat().st_size//1024//1024}MB)"
        )
    except Exception as e:
        log.warning(f"dlib 模型预热失败: {e}（首次刷脸时会重试）")

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
