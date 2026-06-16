"""
ui/widgets/signin_code_dialog.py — 教师端「签到码显示弹窗」(W13+ / W14)

两种 code_type 共享一个 widget：
  - 'digit' → 4 位数字大字 + 倒计时进度条 + 🔄 刷新按钮
  - 'qr'    → 二维码图片(250x250 PNG) + 倒计时进度条 + 🔄 刷新按钮
              + W14: 实时签到列表（QListWidget 顶部追加）+ SigninWebServer 生命周期

行为契约（与 attendance_service.generate_signin_code 配合）:
  1) 打开时立刻调 service 生成码；失败（None）→ QMessageBox + self.close()
  2) 倒计时 = expires_at - now；< 5 秒时刷新按钮标红提示
  3) 点 🔄 再次调 service 覆盖式刷新（service 内 deactivate 旧码）
  4) 倒计时归零**不**自动刷新（对分易式「教师手动触发」语义）
  5) closeEvent 必须 stop timer（防 widget 销毁后 timer 仍跑 → 段错误）
  6) W14: 仅当 code_type='qr' 且传入了 web_server:
     - 二维码内容 = web_server.url（不是裸 token），学生扫码后进 H5 签到页
     - 弹窗 closeEvent 同步 stop web_server（端口不泄漏）
     - 启动 QTimer 每 2 秒轮询 GET /api/signin/status 拉新签到 → 顶部列表

设计取舍:
  - 二维码渲染走 PIL PNG 编码 + QPixmap.loadFromData：
      * 避免 mode='1' → QImage 内存所有权陷阱（QImage 不 copy buffer，
        若传 raw bytes 需 self 上挂 holder 防止 PIL buffer GC 后野指针）
      * QPixmap.loadFromData 内部 decode 并由 Qt 管理 buffer，最稳
  - 不缓存 teacher_window 引用：弹窗只通过 service 调后端，
    教师主窗口关闭/重开时不会悬挂（避免 W6 那种 win 悬挂引用坑）
  - W14: web_server 由 teacher_window._on_open_signin_dialog 提前构造并 start,
    dialog 只持有引用 + 负责 stop。这样 web_server 启动异常时 dialog 不创建,
    避免「半启动状态」。
  - W14: 实时签到列表用 urllib.request（stdlib, 避免 requests 依赖），
    polling QTimer 间隔 2s, 失败一次不打断下次（容错）。
"""
import io
import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QMessageBox, QListWidget, QListWidgetItem,
)

from src.services.attendance_service import AttendanceService

# W14: 实时签到列表轮询周期（毫秒）
POLL_INTERVAL_MS = 2000

log = logging.getLogger(__name__)

# 倒计时刷新周期（毫秒）
TICK_INTERVAL_MS = 1000

# TTL 与「红色警告」阈值
# W15+ 调整: 60s → 300s (5 分钟). 学生扫码 + 输学号密码常超过 60s, 体验差.
#   进度条最大值 = DEFAULT_TTL_SECONDS, 红色警告阈值相应调大.
DEFAULT_TTL_SECONDS = 300
URGENT_THRESHOLD_SECONDS = 30  # 剩余时间 < 此值时刷新按钮变橙 (5 分钟下, 1 分钟就该刷了)

# 样式
_STYLE_BTN_DEFAULT = ""  # 走系统默认
_STYLE_BTN_URGENT = (
    "QPushButton { background-color: #ff8c00; color: white; font-weight: bold; }"
    "QPushButton:hover { background-color: #ff6c00; }"
)


class SigninCodeDialog(QDialog):
    """教师端签到码显示弹窗（数字码 / 二维码共用）。"""

    def __init__(self, parent, task_id: int, code_type: str, teacher_window=None,
                 web_server=None):
        """Args:
            parent: 父 widget（TeacherWindow 自身）
            task_id: 考勤任务 ID
            code_type: 'digit' 或 'qr'
            teacher_window: 暂未使用，预留接口（保持构造签名与任务书一致）
            web_server: W14 新增。SigninWebServer 实例，仅 qr 类型有意义。
                       - 不为 None: 二维码内容用 web_server.url；
                         启动 2s polling 拉新签到；closeEvent 同步 stop()
                       - 为 None: 退化为裸 token 二维码（旧行为，向后兼容）
        """
        super().__init__(parent)
        if code_type not in ("digit", "qr"):
            raise ValueError(f"code_type 必须是 digit/qr，收到 {code_type!r}")
        self.task_id = task_id
        self.code_type = code_type
        self.teacher_window = teacher_window  # noqa: F841 (interface compat)
        # W14: 接收外部 web_server（由 teacher_window 启动并传入）
        # 防退化：web_server 仅在 qr 类型有意义，digit 强制设 None（防御性）
        self.web_server = web_server if code_type == "qr" else None

        # 状态
        self._code_value: str | None = None
        self._expires_at: datetime | None = None
        self._timer: QTimer | None = None
        # W14: 实时签到轮询 timer（仅 qr + web_server 启用）
        self._poll_timer: QTimer | None = None
        self._last_poll_ts: Optional[str] = None  # 增量轮询 since
        self._attendance = AttendanceService()

        # 标题文案
        self._title_text = (
            "🎲 数字签到" if code_type == "digit" else "📱 二维码签到"
        )
        self.setWindowTitle(f"{self._title_text} — 任务 #{task_id}")
        self.setModal(True)
        # W14+ 演示模式: 各模式窗口 +80~100 宽度/+100 高度, 容纳更大二维码和列表
        if code_type == "digit":
            self.resize(440, 380)
        elif self.web_server is not None:
            self.resize(480, 700)  # 加高 160px 放列表 + 大字号
        else:
            self.resize(440, 580)

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

        # W14: 实时签到列表（仅 qr + 有 web_server 时加）。
        # 用 QListWidget 替代 QListView，addItem 自动管理条目。
        if self.code_type == "qr" and self.web_server is not None:
            self._build_realtime_list(layout)

        self.setLayout(layout)

    def _build_realtime_list(self, parent_layout: QVBoxLayout):
        """W14: 构造实时签到列表，挂在进度条下方、工具栏上方。

        列表初始为空，每 2 秒由 _on_poll_status 拉新签到后 append_signin_record 追加。
        """
        # 分组框视觉化（避免裸 QListWidget 在大白板里突兀）
        self.realtime_list = QListWidget()
        self.realtime_list.setMinimumHeight(140)
        self.realtime_list.setMaximumHeight(180)
        self.realtime_list.setStyleSheet(
            "QListWidget {"
            " background-color: #F8FAFC; border: 1px solid #E5E7EB;"
            " border-radius: 6px; padding: 4px;"
            " font-size: 12px;"
            "}"
            "QListWidget::item { padding: 4px 8px; }"
        )
        # 标题行
        header = QLabel("📥 实时签到列表")
        header.setStyleSheet(
            "color: #1E293B; font-weight: 600; font-size: 12px; padding-top: 4px;"
        )
        parent_layout.addWidget(header)
        parent_layout.addWidget(self.realtime_list)

    # -----------------------------------------------------
    # 码生成 / 渲染
    # -----------------------------------------------------
    def _generate_code(self):
        """调 service 生成码。失败弹窗并关闭；成功更新 UI + 启 timer。

        W14: 注意 web_server 已经由 teacher_window 提前生成 token 并启动,
        这里 service 端可能复用同一 token（generate_signin_code 会 deactivate
        旧码再写新码, 所以会替换 web_server 持有的旧 token）。
        妥协: W14 阶段保持 service 端调用不动, 接受「刷新时 web_server 持有的
        旧 token 立即失效」的语义（H5 端会显示「签到码已失效」）。如要更平滑
        的体验需把 web_server.token 也同步更新, 留 W15+ 优化。
        """
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

        # W15+ 修复: dialog 内 _generate_code() 后必须同步 web_server.token,
        # 否则:
        #   - teacher_window._on_open_signin_dialog 已经 generate + 启 web_server
        #   - dialog 启动时 (__init__ 末尾) 又 _generate_code 一次, DB 旧 token deactive
        #   - web_server 内存 token 跟 DB LIVE 不一致 → 二维码 URL 错误
        #   - 学生扫到错 URL → 提交 CODE_INVALID
        # 同步后, web_server.url = 新 token URL, 二维码内容正确.
        if self.web_server is not None and self._code_value:
            try:
                self.web_server.update_token(self._code_value)
            except Exception as e:
                log.exception("dialog 启动时 web_server.update_token 失败: %s", e)

        # 第一次渲染完立刻更新一次倒计时（避免开弹窗那一秒进度条还显示 60）
        self._update_countdown()

        # 启动每秒 tick
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.timeout.connect(self._on_tick)
        self._timer.start(TICK_INTERVAL_MS)

        # W14: 第一次生成码后, 如果有 web_server, 启动实时签到轮询
        if self.web_server is not None and self._poll_timer is None:
            self.start_polling_status(interval_ms=POLL_INTERVAL_MS)

    # -----------------------------------------------------
    # W14: 实时签到轮询
    # -----------------------------------------------------
    def start_polling_status(self, interval_ms: int = POLL_INTERVAL_MS):
        """W14: 启动 QTimer 每 N 毫秒拉一次 GET /api/signin/status, 把新签到
        追加到 realtime_list。

        设计选择:
          - 用 urllib.request (stdlib), 避免引入 requests 依赖
          - 单次失败不打断下次 tick（异常 swallowed + log.debug）
          - since 自增：每拉到一条新记录, _last_poll_ts 更新到该条 sign_in_time,
            下次 GET 只拿更新部分
        """
        if self._poll_timer is not None:
            log.debug("polling timer 已在运行, 跳过重复 start")
            return
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_poll_status)
        self._poll_timer.start(interval_ms)
        log.info("W14 实时签到轮询已启动: interval=%sms", interval_ms)

    def _on_poll_status(self):
        """QTimer tick: GET /api/signin/status?task=&since= → 追加 new_records。"""
        if self.web_server is None:
            return
        port = getattr(self.web_server, "port", None)
        if port is None:
            return
        url = f"http://127.0.0.1:{port}/api/signin/status"
        params = f"task={self.task_id}"
        if self._last_poll_ts:
            from urllib.parse import quote
            params += f"&since={quote(self._last_poll_ts)}"
        full_url = f"{url}?{params}"
        try:
            req = urllib.request.Request(full_url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                payload = resp.read().decode("utf-8")
            data = json.loads(payload)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError,
                json.JSONDecodeError, OSError) as e:
            # 失败一次不打断: 网络抖动 / 端口未就绪 / 服务关了都是常见情况
            log.debug("轮询 GET %s 失败: %s", full_url, e)
            return
        except Exception as e:
            log.debug("轮询意外失败: %s", e)
            return

        if not data.get("ok"):
            return
        records = data.get("new_records") or []
        for rec in records:
            self.append_signin_record(rec)
            # 更新 since 为最新一条的 sign_in_time（增量轮询）
            ts = rec.get("sign_in_time")
            if ts:
                self._last_poll_ts = ts

    def append_signin_record(self, rec: dict):
        """W14: 把一条新签到记录追加到 realtime_list 顶部。

        rec 期望字段: student_name / status / sign_in_time / signin_method
        """
        if not hasattr(self, "realtime_list"):
            return
        student_name = rec.get("student_name") or "未知"
        ts = rec.get("sign_in_time") or ""
        # 截短时间到 HH:MM:SS（后端 isoformat 含日期+秒）
        short_ts = ts[11:19] if len(ts) >= 19 else ts
        status = rec.get("status") or ""
        method = rec.get("signin_method") or ""
        # ✓/✗ 用 status 区分
        glyph = "✓" if status in ("present", "late") else "✗"
        # 行格式: ✓ 张三  18:09:33  [qr]  准时
        method_zh = {"qr": "扫码", "face": "刷脸", "digit": "数字码"}.get(method, method)
        status_zh = {"present": "准时", "late": "迟到", "absent": "缺勤"}.get(status, status)
        item_text = f"{glyph} {student_name}  {short_ts}  [{method_zh}]  {status_zh}"
        item = QListWidgetItem(item_text)
        # 颜色：present 绿 / late 橙 / 其他默认
        if status == "present":
            item.setForeground(Qt.darkGreen)
        elif status == "late":
            item.setForeground(Qt.darkYellow)
        # 顶部插入（最新在最上面）
        self.realtime_list.insertItem(0, item)

    def _render_code(self):
        """把 self._code_value 渲染到 self.code_label。

        W14: 当 web_server 不为 None 时，二维码内容用 web_server.url（学生扫码后
        进 H5 签到页），而不是裸 token。防御性兜底：无 web_server 时仍走裸 token
        （向后兼容）。
        """
        if self.code_type == "digit":
            # 4 位数字加空格分隔便于辨认
            display = " ".join(self._code_value)
            self.code_label.setText(display)
        else:
            # 决定二维码内容：优先用 web_server.url，兜底裸 token
            if self.web_server is not None:
                display_value = self.web_server.url
            else:
                display_value = self._code_value
            try:
                import qrcode  # 局部 import：仅二维码路径才用
                # W14+ 演示模式: 二维码 250→280, 投影清晰
                qr_img = qrcode.make(display_value).resize((280, 280))
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
                    log.error(
                        "QPixmap.loadFromData 失败, display_value=%s",
                        display_value,
                    )
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
        """教师点 🔄 重新生成码（覆盖旧码）。
        
        W15+ 修复: 同步调 web_server.update_token(), 否则:
          - _generate_code 只更新 self._code_value
          - web_server.token 仍是旧值, self.web_server.url 不变
          - _render_code 用 web_server.url 渲染的二维码图片内容不变
          → 学生扫码还是老 URL, 刷新无效
        """
        self._generate_code()
        # W15+: 同步 web_server.token (二码码内容立刻跟刷新走)
        if self.web_server is not None and self._code_value:
            try:
                self.web_server.update_token(self._code_value)
            except Exception as e:
                log.exception("web_server.update_token 失败, 二维码可能仍是旧 URL: %s", e)

    # -----------------------------------------------------
    # 销毁
    # -----------------------------------------------------
    def closeEvent(self, event):
        """关闭弹窗时停 timer，避免 widget 销毁后 timer 仍触发 → 段错误。

        W14: 同时停 web_server（端口释放）和 polling timer。
        """
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        # W14: 关弹窗时停 polling timer
        if self._poll_timer is not None:
            try:
                self._poll_timer.stop()
            except Exception as e:
                log.debug("停 polling timer 失败: %s", e)
            self._poll_timer = None
        # W14: 关弹窗时同步停 SigninWebServer（端口释放，daemon 线程兜底）
        if self.web_server is not None:
            try:
                self.web_server.stop()
                log.info("SigninWebServer 已停止 (dialog close)")
            except Exception as e:
                log.exception("停 SigninWebServer 失败: %s", e)
            self.web_server = None
        super().closeEvent(event)
