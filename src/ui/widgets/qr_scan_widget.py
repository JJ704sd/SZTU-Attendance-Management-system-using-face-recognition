"""
ui/widgets/qr_scan_widget.py — 学生端「二维码扫描」子 Tab

W13+ 二维码签到方式 UI:
  - 自带 CameraWidget (复用 camera_widget.py) 抓帧
  - 500ms QTimer 调 capture_one_frame() 取 BGR 帧
  - cv2.QRCodeDetector().detectAndDecode() 解码
  - 解码出 8~64 字符的 base64 token → 调 attendance_service.sign_in_by_qr
  - 成功 → 状态 label 显示「✅ 出勤 / ⚠️ 迟到」, stop timer, 发 signin_succeeded

设计要点:
  - qr_token 由教师端 generate_signin_code(task_id, 'qr') 生成, 22 字符 base64.
  - service 边界校验包含 8~64 长度, UI 这边也补一层（防 garbage 触发后端）.
  - closeEvent 必须 stop timer + pause camera —— 跟 student_window._cleanup_resources 模式一致.
  - 摄像头释放交给 CameraWidget.stop(), 父窗口 close 时会触发子 widget closeEvent.
"""
import logging
from typing import Optional

import cv2
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)

from src.services.attendance_service import AttendanceService
from src.ui.widgets.camera_widget import CameraWidget

log = logging.getLogger(__name__)

# 状态展示文案（跟 DigitSigninWidget 一致）
_STATUS_TEXT = {
    "present": "✅ 出勤",
    "late":    "⚠️ 迟到",
}

# 扫描间隔: 500ms = 2 fps. 太快 CPU 跑满, 太慢体验差.
SCAN_INTERVAL_MS = 500

# QR token 长度边界 (跟 attendance_service.sign_in_by_qr 对齐: 8~64)
QR_MIN_LEN = 8
QR_MAX_LEN = 64


class QrScanWidget(QWidget):
    """学生端「二维码扫描签到」子 Tab 控件.

    构造参数:
        parent:              父窗口（一般传 StudentWindow）
        task_id:             当前选中的考勤任务 id
        user_id:             当前登录学生 id
        attendance_service:  业务服务实例

    Signals:
        signin_succeeded(record): 签到成功, 携带 AttendanceRecord
    """

    signin_succeeded = pyqtSignal(object)  # AttendanceRecord

    def __init__(self, parent: QWidget,
                 task_id: int,
                 user_id: int,
                 attendance_service: AttendanceService):
        super().__init__(parent)
        self._task_id = task_id
        self._user_id = user_id
        self._attendance_service = attendance_service
        self._qr_detector = cv2.QRCodeDetector()
        self._scanning = False

        self._init_ui()
        # 构造完就尝试启动摄像头 + 扫描 timer (跟 DigitSigninWidget 自动聚焦同理:
        # 学生切到「二维码」Tab 就能扫, 不必再点「开始」).
        # 如果摄像头被别处占用, _start_scan() 内部会优雅降级.

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # 提示文字
        hint = QLabel("📷 请将摄像头对准教师二维码")
        hint.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F2937;")
        layout.addWidget(hint)

        sub_hint = QLabel(
            f"扫描到有效二维码即自动签到\n任务 ID: #{self._task_id}"
        )
        sub_hint.setStyleSheet("color: #6B7280; font-size: 12px;")
        sub_hint.setWordWrap(True)
        layout.addWidget(sub_hint)

        # 摄像头
        self.camera = CameraWidget()
        self.camera.setMinimumSize(480, 360)
        layout.addWidget(self.camera)

        # 状态
        self.status_label = QLabel("等待启动扫描...")
        self.status_label.setProperty("role", "status")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)
        layout.addWidget(self.status_label)

        # 按钮
        btn_row = QHBoxLayout()
        self.open_cam_btn = QPushButton("打开摄像头")
        self.open_cam_btn.setProperty("role", "primary")
        self.open_cam_btn.clicked.connect(self._on_open_cam)
        btn_row.addWidget(self.open_cam_btn)
        self.start_scan_btn = QPushButton("开始扫描")
        self.start_scan_btn.setProperty("role", "primary")
        self.start_scan_btn.clicked.connect(self._on_start_scan_clicked)
        self.start_scan_btn.setEnabled(False)
        btn_row.addWidget(self.start_scan_btn)
        self.stop_scan_btn = QPushButton("停止扫描")
        self.stop_scan_btn.clicked.connect(self._on_stop_scan_clicked)
        self.stop_scan_btn.setEnabled(False)
        btn_row.addWidget(self.stop_scan_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        self.setLayout(layout)

        # 扫描 timer —— 跟 DigitSigninWidget 不同, 这里 timer 是 self 的,
        # 不在构造时 start, 等用户点「开始扫描」再开.
        self._scan_timer = QTimer(self)
        self._scan_timer.setInterval(SCAN_INTERVAL_MS)
        self._scan_timer.timeout.connect(self._on_tick)

    # ------------------ 用户操作 ------------------
    def _on_open_cam(self):
        if self.camera.is_running():
            self.camera.stop()
            self.open_cam_btn.setText("打开摄像头")
            self.start_scan_btn.setEnabled(False)
            self._stop_scan_internal()
        else:
            ok = self.camera.start(0)
            if ok:
                self.open_cam_btn.setText("关闭摄像头")
                self.start_scan_btn.setEnabled(True)
                self._set_status("摄像头就绪，点击「开始扫描」", "neutral")
            else:
                self._set_status("❌ 摄像头打开失败", "error")

    def _on_start_scan_clicked(self):
        if not self.camera.is_running():
            self._set_status("⚠️ 请先打开摄像头", "error")
            return
        self._start_scan_internal()

    def _on_stop_scan_clicked(self):
        self._stop_scan_internal()

    # ------------------ 内部启停 ------------------
    def _start_scan_internal(self):
        if self._scanning:
            return
        self._scanning = True
        self._scan_timer.start()
        self.start_scan_btn.setEnabled(False)
        self.stop_scan_btn.setEnabled(True)
        self._set_status("🔍 扫描中...", "neutral")

    def _stop_scan_internal(self):
        if not self._scanning:
            return
        self._scanning = False
        self._scan_timer.stop()
        self.start_scan_btn.setEnabled(self.camera.is_running())
        self.stop_scan_btn.setEnabled(False)

    # ------------------ 扫描主循环 ------------------
    def _on_tick(self):
        """500ms 一次: 抓一帧 → QR decode → 命中就签到."""
        if not self._scanning or not self.camera.is_running():
            return

        frame = self.camera.capture_one_frame()
        if frame is None:
            return

        # 防御性: shape 异常时跳过
        if frame.ndim != 3 or frame.shape[2] != 3:
            return

        # capture_one_frame() 返回 BGR (见 camera_widget.py:147 docstring).
        # cv2.QRCodeDetector 不挑剔色彩空间, BGR/RGB/灰度都行, 直接喂.
        try:
            data, bbox, _ = self._qr_detector.detectAndDecode(frame)
        except Exception as e:
            log.warning("QRCodeDetector.detectAndDecode 异常: %s", e)
            return

        if not data:
            # 解码空: 不刷 status (避免闪烁), 但短暂显示一下「扫描中」
            return

        # 防垃圾输入: 长度不在 8~64 直接忽略, 不发后端
        if not (QR_MIN_LEN <= len(data) <= QR_MAX_LEN):
            log.info("QR 解码出非预期长度 (%d) 数据, 忽略", len(data))
            return

        # 命中且长度合理 → 调业务
        self._stop_scan_internal()  # 防止 timer 在 service 调用期间继续触发
        try:
            record = self._attendance_service.sign_in_by_qr(
                self._task_id, self._user_id, data,
            )
        except Exception as e:
            log.exception("二维码签到异常")
            self._set_status(f"❌ 签到异常：{e}", "error")
            return

        if record is None:
            # None = token 无效/已过期/已签到/任务已关闭
            self._set_status("❌ 二维码无效或已过期", "error")
            # 失败不 restart scan, 让用户点「开始扫描」再试
            return

        # 成功
        text = _STATUS_TEXT.get(record.status, f"✅ 签到成功（{record.status}）")
        self._set_status(text, "success")
        self.signin_succeeded.emit(record)

    # ------------------ 资源 + 状态 ------------------
    def _set_status(self, text: str, state: str):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def closeEvent(self, event):
        """父窗口 close 时会触发本 widget closeEvent, 释放资源."""
        self._stop_scan_internal()
        # pause 而非 stop: 让父窗口若复用 camera (跟 CameraWidget _lock 互斥) 仍可读.
        # 但本 widget 是子 Tab 独占 camera, 父窗口没别的消费者, 所以直接 stop 更安全.
        try:
            if self.camera.is_running():
                self.camera.stop()
        except Exception:
            log.exception("QrScanWidget.closeEvent 释放 camera 异常")
        super().closeEvent(event)

    # ------------------ 父窗口辅助 ------------------
    def reset_for_new_task(self, task_id: int):
        """父窗口切换 task 时调用 —— 重置 widget 状态但**不**重启扫描
        (让用户重新点「开始扫描」明确意图, 避免上一个 task 的 token 误签到新 task)."""
        self._stop_scan_internal()
        self._task_id = task_id
        self._set_status(f"已切换到任务 #{task_id}，点击「开始扫描」", "neutral")
