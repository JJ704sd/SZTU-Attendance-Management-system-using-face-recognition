"""
ui/widgets/camera_widget.py — 摄像头预览控件

Phase 2 范围：
- 内部持 cv2.VideoCapture
- QTimer 30 ms 间隔拉帧 → 转 QImage（rgbSwapped）→ 缩放贴 QLabel
- frame_ready 信号上发 BGR ndarray（face_helper 链路消费 BGR）
- start(device_id=0) -> bool，打不开返回 False 并在控件上盖红色"摄像头不可用"
- stop() / capture_one_frame() / closeEvent / __del__ 兜底释放
- 不做人脸框叠加（留给 Phase 5）
"""
import logging

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

log = logging.getLogger(__name__)


class CameraWidget(QWidget):
    frame_ready = pyqtSignal(np.ndarray)  # BGR frame, shape (H, W, 3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cap: cv2.VideoCapture | None = None
        self._timer: QTimer | None = None
        self._lock = False  # 简易并发保险：capture_one_frame 与 _on_tick 互斥
        self._init_ui()

    def _init_ui(self):
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self._label = QLabel("摄像头未启动")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("color: gray; background-color: #0F172A;")
        self._label.setMinimumSize(320, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

    # -----------------------------------------------------
    # 生命周期
    # -----------------------------------------------------
    def start(self, device_id: int = 0) -> bool:
        """打开摄像头并开始 30 fps 预览。返回是否成功。"""
        if self._cap is not None and self._cap.isOpened():
            return True
        cap = cv2.VideoCapture(device_id)
        if not cap.isOpened():
            cap.release()
            self._show_unavailable()
            return False
        self._cap = cap
        self._label.setStyleSheet("color: white; background-color: #0F172A;")
        self._label.setText("")

        self._timer = QTimer(self)
        self._timer.setInterval(30)  # ~33 fps
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()
        return True

    def stop(self):
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._label.setText("摄像头已停止")
        self._label.setStyleSheet("color: gray; background-color: #0F172A;")

    def capture_one_frame(self) -> np.ndarray | None:
        """同步抓一帧（BGR）。Phase 3 collect_for_user 在工作线程里调。
        与 _on_tick 互斥，避免 cv2.VideoCapture 并发读帧。"""
        if self._cap is None or not self._cap.isOpened():
            return None
        if self._lock:
            return None
        self._lock = True
        try:
            ok, frame = self._cap.read()
            return frame if ok else None
        finally:
            self._lock = False

    def is_running(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def closeEvent(self, event):
        self.stop()
        super().closeEvent(event)

    def __del__(self):
        # 兜底：万一 closeEvent 没触发
        try:
            if self._cap is not None:
                self._cap.release()
        except Exception:
            pass

    # -----------------------------------------------------
    # 内部
    # -----------------------------------------------------
    def _on_tick(self):
        frame = self.capture_one_frame()
        if frame is None:
            return
        self._render_frame(frame)
        self.frame_ready.emit(frame)

    def _render_frame(self, bgr: np.ndarray):
        h, w, ch = bgr.shape
        bytes_per_line = ch * w
        # QImage 用 BGR888 格式持有 cv2 缓冲；rgbSwapped 转成 Qt 期望的 RGB
        q_img = QImage(bgr.data, w, h, bytes_per_line, QImage.Format_BGR888).rgbSwapped()
        pixmap = QPixmap.fromImage(q_img).scaled(
            self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._label.setPixmap(pixmap)

    def _show_unavailable(self):
        self._label.setText("⚠ 摄像头不可用\n请检查摄像头是否被其他程序占用")
        self._label.setStyleSheet(
            "color: #DC2626; background-color: #FEE2E2; "
            "font-size: 14px; padding: 20px;"
        )
