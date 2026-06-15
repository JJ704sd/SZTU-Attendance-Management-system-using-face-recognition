"""
ui/widgets/signin_code_dialog.py — 教师端「签到码显示弹窗」(W13+)

两种 code_type 共享一个 widget：
  - 'digit' → 4 位数字大字 + 倒计时进度条 + 🔄 刷新按钮
  - 'qr'    → 二维码图片(250x250 PNG) + 倒计时进度条 + 🔄 刷新按钮

行为契约（与 attendance_service.generate_signin_code 配合）:
  1) 打开时立刻调 service 生成码；失败（None）→ QMessageBox + self.close()
  2) 倒计时 = expires_at - now；< 5 秒时刷新按钮标红提示
  3) 点 🔄 再次调 service 覆盖式刷新（service 内 deactivate 旧码）
  4) 倒计时归零**不**自动刷新（对分易式「教师手动触发」语义）
  5) closeEvent 必须 stop timer（防 widget 销毁后 timer 仍跑 → 段错误）

设计取舍:
  - 二维码渲染走 PIL PNG 编码 + QPixmap.loadFromData：
      * 避免 mode='1' → QImage 内存所有权陷阱（QImage 不 copy buffer，
        若传 raw bytes 需 self 上挂 holder 防止 PIL buffer GC 后野指针）
      * QPixmap.loadFromData 内部 decode 并由 Qt 管理 buffer，最稳
  - 不缓存 teacher_window 引用：弹窗只通过 service 调后端，
    教师主窗口关闭/重开时不会悬挂（避免 W6 那种 win 悬挂引用坑）
"""
import io
import logging
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox,
)

from src.services.attendance_service import AttendanceService

log = logging.getLogger(__name__)

# 倒计时刷新周期（毫秒）
TICK_INTERVAL_MS = 1000

# TTL 与「红色警告」阈值（与 service 一致：DEFAULT_CODE_TTL_SECONDS=60）
DEFAULT_TTL_SECONDS = 60
URGENT_THRESHOLD_SECONDS = 5  # 剩余时间 < 此值时刷新按钮变橙

# 样式
_STYLE_BTN_DEFAULT = ""  # 走系统默认
_STYLE_BTN_URGENT = (
    "QPushButton { background-color: #ff8c00; color: white; font-weight: bold; }"
    "QPushButton:hover { background-color: #ff6c00; }"
)


class SigninCodeDialog(QDialog):
    """教师端签到码显示弹窗（数字码 / 二维码共用）。"""

    def __init__(self, parent, task_id: int, code_type: str, teacher_window=None):
        """Args:
            parent: 父 widget（TeacherWindow 自身）
            task_id: 考勤任务 ID
            code_type: 'digit' 或 'qr'
            teacher_window: 暂未使用，预留接口（保持构造签名与任务书一致）
        """
        super().__init__(parent)
        if code_type not in ("digit", "qr"):
            raise ValueError(f"code_type 必须是 digit/qr，收到 {code_type!r}")
        self.task_id = task_id
        self.code_type = code_type
        self.teacher_window = teacher_window  # noqa: F841 (interface compat)

        # 状态
        self._code_value: str | None = None
        self._expires_at: datetime | None = None
        self._timer: QTimer | None = None
        self._attendance = AttendanceService()

        # 标题文案
        self._title_text = (
            "🎲 数字签到" if code_type == "digit" else "📱 二维码签到"
        )
        self.setWindowTitle(f"{self._title_text} — 任务 #{task_id}")
        self.setModal(True)
        # 数字码窗口小一点，二维码要 250x250 图片所以略大
        self.resize(360, 280) if code_type == "digit" else self.resize(360, 480)

        self._init_ui()

        # 第一次生成（失败则 self.close()）
        self._generate_code()

    # -----------------------------------------------------
    # UI 构建
    # -----------------------------------------------------
    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # 顶部提示
        self.info_label = QLabel(
            f"{self._title_text}\n请在倒计时结束前让学生提交此码"
        )
        self.info_label.setAlignment(Qt.AlignCenter)
        info_font = QFont()
        info_font.setPointSize(10)
        self.info_label.setFont(info_font)
        self.info_label.setStyleSheet("color: gray; padding: 4px;")
        layout.addWidget(self.info_label)

        # 码显示区：数字码 4 位超大字号 / 二维码 250x250
        if self.code_type == "digit":
            self.code_label = QLabel("····")
            code_font = QFont()
            code_font.setPointSize(48)
            code_font.setBold(True)
            self.code_label.setFont(code_font)
            self.code_label.setAlignment(Qt.AlignCenter)
            self.code_label.setStyleSheet(
                "color: #1a73e8; letter-spacing: 12px; padding: 16px;"
                "border: 2px dashed #1a73e8; border-radius: 8px;"
            )
            self.code_label.setMinimumHeight(100)
            layout.addWidget(self.code_label)
        else:  # qr
            self.code_label = QLabel("加载中...")
            self.code_label.setAlignment(Qt.AlignCenter)
            self.code_label.setMinimumSize(260, 260)
            self.code_label.setMaximumSize(280, 280)
            self.code_label.setStyleSheet(
                "border: 1px solid #ccc; background: white; padding: 4px;"
            )
            layout.addWidget(self.code_label, alignment=Qt.AlignCenter)

        # 倒计时进度条（max=TTL, value=remaining, 倒着走）
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(DEFAULT_TTL_SECONDS)
        self.progress_bar.setValue(DEFAULT_TTL_SECONDS)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("剩 %v 秒")
        layout.addWidget(self.progress_bar)

        # 倒计时文字
        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("color: gray;")
        layout.addWidget(self.countdown_label)

        # 工具栏
        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 刷新码")
        self.refresh_btn.setMinimumHeight(36)
        self.refresh_btn.clicked.connect(self._on_refresh)
        self.close_btn = QPushButton("关闭")
        self.close_btn.setMinimumHeight(36)
        self.close_btn.clicked.connect(self.accept)
        toolbar.addStretch()
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.close_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.setLayout(layout)

    # -----------------------------------------------------
    # 码生成 / 渲染
    # -----------------------------------------------------
    def _generate_code(self):
        """调 service 生成码。失败弹窗并关闭；成功更新 UI + 启 timer。"""
        try:
            result = self._attendance.generate_signin_code(
                self.task_id, self.code_type, ttl_seconds=DEFAULT_TTL_SECONDS,
            )
        except ValueError as e:
            log.warning("generate_signin_code 参数错: %s", e)
            QMessageBox.warning(self.parent(), "生成失败", str(e))
            self.close()
            return
        except Exception as e:
            log.exception("generate_signin_code 异常: %s", e)
            QMessageBox.warning(self.parent(), "生成失败", "请确认任务状态为 open")
            self.close()
            return

        if result is None:
            QMessageBox.warning(self.parent(), "生成失败", "请确认任务状态为 open")
            self.close()
            return

        self._code_value = result["code"]
        self._expires_at = result["expires_at"]
        self._render_code()

        # 第一次渲染完立刻更新一次倒计时（避免开弹窗那一秒进度条还显示 60）
        self._update_countdown()

        # 启动每秒 tick
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_tick)
        self._timer.start(TICK_INTERVAL_MS)

    def _render_code(self):
        """把 self._code_value 渲染到 self.code_label。"""
        if self.code_type == "digit":
            # 4 位数字加空格分隔便于辨认
            display = " ".join(self._code_value)
            self.code_label.setText(display)
        else:
            try:
                import qrcode  # 局部 import：仅二维码路径才用
                qr_img = qrcode.make(self._code_value).resize((250, 250))
                buf = io.BytesIO()
                # 必须先转 RGB 再存 PNG：qrcode 默认是 mode='1'，PIL PNG encoder 对
                # 1-bit 也能写，但 'RGB' 更通用（避免某些 PIL 版本对 '1' 模式的
                # palette 处理差异），且尺寸完全可控。
                qr_img.convert("RGB").save(buf, format="PNG")
                pix = QPixmap()
                ok = pix.loadFromData(buf.getvalue(), "PNG")
                if ok and not pix.isNull():
                    self.code_label.setPixmap(pix)
                    self.code_label.setText("")  # 清除「加载中...」
                else:
                    self.code_label.setText("⚠️ 二维码加载失败")
                    log.error("QPixmap.loadFromData 失败, code_value=%s", self._code_value)
            except Exception as e:
                log.exception("二维码渲染失败: %s", e)
                self.code_label.setText(f"⚠️ 渲染失败：{e}")

    # -----------------------------------------------------
    # 倒计时
    # -----------------------------------------------------
    def _update_countdown(self):
        """根据 expires_at 算剩余秒数，更新进度条 + 文字 + 按钮样式。"""
        if self._expires_at is None:
            return
        remaining = max(0, int((self._expires_at - datetime.now()).total_seconds()))
        # 进度条：value=remaining（max=TTL=60）
        self.progress_bar.setValue(remaining)
        # 倒计时文字
        if remaining > 0:
            self.countdown_label.setText(f"剩余 {remaining} 秒后失效")
        else:
            self.countdown_label.setText("⏰ 码已失效，请点 🔄 刷新")

        # 按钮样式：< 5 秒变橙
        if remaining <= URGENT_THRESHOLD_SECONDS:
            if self.refresh_btn.styleSheet() != _STYLE_BTN_URGENT:
                self.refresh_btn.setStyleSheet(_STYLE_BTN_URGENT)
        else:
            if self.refresh_btn.styleSheet() != _STYLE_BTN_DEFAULT:
                self.refresh_btn.setStyleSheet(_STYLE_BTN_DEFAULT)

    def _on_tick(self):
        """QTimer 每秒回调：更新倒计时；到 0 时停 timer。"""
        if self._expires_at is None:
            return
        self._update_countdown()
        if datetime.now() >= self._expires_at:
            # 倒计时归零 → 停 timer，不自动刷新
            if self._timer is not None:
                self._timer.stop()
            log.info("签到码 #%s 已过期, 等待教师手动刷新", self.task_id)

    # -----------------------------------------------------
    # 用户操作
    # -----------------------------------------------------
    def _on_refresh(self):
        """教师点 🔄 重新生成码（覆盖旧码）。"""
        self._generate_code()

    # -----------------------------------------------------
    # 销毁
    # -----------------------------------------------------
    def closeEvent(self, event):
        """关闭弹窗时停 timer，避免 widget 销毁后 timer 仍触发 → 段错误。"""
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        super().closeEvent(event)
