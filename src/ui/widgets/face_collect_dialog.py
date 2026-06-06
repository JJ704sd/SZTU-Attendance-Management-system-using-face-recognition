"""
ui/widgets/face_collect_dialog.py — 人脸采集对话框

Phase 5：学生端 Tab 1「人脸注册」调用，弹模态对话框采 N 张。

设计要点（CLAUDE.md 已警告过）：
- 采集在子线程跑（QThread + QObject worker），进度通过 pyqtSignal
  跨线程。connect 默认是 QueuedConnection（跨线程），所以可以直接
  setText/setValue 不会段错误。
- 采集时停掉 CameraWidget 的 preview QTimer，让 worker 独占
  cv2.VideoCapture。worker 通过 _WorkerCamera 最小接口喂给
  FaceService.collect_for_user() —— 复用现成逻辑，零重复实现。
- 用户取消：threading.Event 触发 stop_event，collect_for_user
  下一轮循环立即返回 {"ok": False, "error": "用户取消"}。
"""
import logging
import threading
from typing import Optional

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox,
)

from src.config import Config
from src.models.user import User

log = logging.getLogger(__name__)


class _WorkerCamera:
    """collect_for_user 需要的最小 camera 接口；worker 持 cap 直读，无 race。"""
    def __init__(self, cap: cv2.VideoCapture):
        self._cap = cap

    def is_running(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def capture_one_frame(self):
        if self._cap is None or not self._cap.isOpened():
            return None
        ok, frame = self._cap.read()
        return frame if ok else None


class _CollectWorker(QObject):
    """子线程跑 face_service.collect_for_user。"""
    progress = pyqtSignal(int, int)   # captured, total
    finished = pyqtSignal(dict)        # collect_for_user 返回的 dict
    error = pyqtSignal(str)

    def __init__(self, user_id: int, cap: cv2.VideoCapture, n_samples: int,
                 stop_event: threading.Event):
        super().__init__()
        self.user_id = user_id
        self.cap = cap
        self.n_samples = n_samples
        self.stop_event = stop_event

    def run(self):
        try:
            from src.services.face_service import FaceService, _FaceCache
            camera = _WorkerCamera(self.cap)
            result = FaceService().collect_for_user(
                self.user_id, camera,
                n_samples=self.n_samples,
                on_progress=lambda c, t: self.progress.emit(c, t),
                cache=_FaceCache.get(),
                stop_event=self.stop_event,
            )
            self.finished.emit(result)
        except Exception as e:
            log.exception("采集 worker 异常")
            self.error.emit(str(e))


class FaceCollectDialog(QDialog):
    """模态对话框，采集 N 张人脸编码。

    用法：
        dlg = FaceCollectDialog(user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            n = dlg.saved_count  # 实际入库的张数

    成功 accept() / 失败或取消 reject()。"""

    def __init__(self, user: User, parent=None):
        super().__init__(parent)
        self.user = user
        self.saved_count = 0
        self._camera_widget = None
        self._thread: Optional[QThread] = None
        self._worker: Optional[_CollectWorker] = None
        self._stop_event: Optional[threading.Event] = None
        self._collecting = False
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("人脸采集")
        self.setModal(True)
        self.resize(640, 560)

        layout = QVBoxLayout()

        # 顶部说明
        intro = QLabel(
            f"需采集 {Config.FACE_SAMPLE_COUNT} 张不同角度的人脸。\n"
            f"请缓慢转头，确保光线充足、人脸在画面中央。"
        )
        intro.setStyleSheet("color: gray; padding: 6px;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # 摄像头预览（含人脸框 overlay）
        from src.ui.widgets.camera_widget import CameraWidget
        self._camera_widget = CameraWidget()
        self._camera_widget.setMinimumSize(480, 360)
        cam_ok = self._camera_widget.start(0)
        if cam_ok:
            self._camera_widget.set_overlay_callback(self._draw_face_boxes)
        layout.addWidget(self._camera_widget)

        # 状态标签（必须先创建，后面 _set_status 才能用）
        self.status_label = QLabel("")
        self.status_label.setObjectName("status")
        self.status_label.setProperty("role", "status")
        layout.addWidget(self.status_label)
        if not cam_ok:
            self._set_status("摄像头不可用，无法采集", state="error")
        else:
            self._set_status("就绪 — 点击「开始采集」", state="neutral")

        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, Config.FACE_SAMPLE_COUNT)
        self.progress.setValue(0)
        self.progress.setFormat("%v / %m")
        layout.addWidget(self.progress)

        # 按钮
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("开始采集")
        self.start_btn.setProperty("role", "primary")
        self.start_btn.clicked.connect(self._on_start)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.start_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

        self.setLayout(layout)
        self._refresh_button_state()

    def _draw_face_boxes(self, bgr: np.ndarray) -> np.ndarray:
        """CameraWidget overlay 回调：在每帧上画人脸框（绿框）。"""
        try:
            from src.utils.face_helper import face_locations
            locs = face_locations(bgr)
            for (top, right, bottom, left) in locs:
                cv2.rectangle(bgr, (left, top), (right, bottom), (0, 255, 0), 2)
                cv2.putText(bgr, "Face", (left, top - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        except Exception:
            log.exception("画人脸框异常")
        return bgr

    # ------------------------------------------------------------------
    # 状态切换
    # ------------------------------------------------------------------
    def _refresh_button_state(self):
        cam_ok = self._camera_widget is not None and self._camera_widget.is_running()
        self.start_btn.setEnabled(cam_ok and not self._collecting)
        self.cancel_btn.setText("取消" if not self._collecting else "中止")

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        # 触发 dynamic property 重新应用 QSS
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    # ------------------------------------------------------------------
    # 采集控制
    # ------------------------------------------------------------------
    def _on_start(self):
        if self._collecting:
            return
        cap = self._camera_widget.get_cap() if self._camera_widget else None
        if cap is None or not cap.isOpened():
            QMessageBox.warning(self, "提示", "摄像头未启动，无法采集")
            return

        # 暂停 preview QTimer，腾出 cap 给 worker
        self._camera_widget.stop()

        # 起 worker
        self._stop_event = threading.Event()
        self._thread = QThread(self)
        self._worker = _CollectWorker(
            self.user.id, cap, Config.FACE_SAMPLE_COUNT, self._stop_event,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress, Qt.QueuedConnection)
        self._worker.finished.connect(self._on_finished, Qt.QueuedConnection)
        self._worker.error.connect(self._on_error, Qt.QueuedConnection)
        # 资源回收
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.start()

        self._collecting = True
        self._set_status("采集中...", state="neutral")
        self._refresh_button_state()

    @pyqtSlot(int, int)
    def _on_progress(self, captured: int, total: int):
        self.progress.setValue(captured)
        self._set_status(f"已采集 {captured} / {total} 张，请继续转头...", state="neutral")

    @pyqtSlot(dict)
    def _on_finished(self, result: dict):
        self._collecting = False
        self.saved_count = result.get("saved", 0)
        if result.get("ok"):
            self._set_status(f"完成！共采集 {self.saved_count} 张", state="success")
            self._refresh_button_state()
            # 不立即 accept；让用户看完进度再点取消关闭
        else:
            err = result.get("error", "未知错误")
            if err == "用户取消":
                self._set_status(
                    f"已取消（采集 {self.saved_count} 张后中止）", state="neutral",
                )
            else:
                self._set_status(f"失败：{err}", state="error")
            self._refresh_button_state()

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._collecting = False
        self._set_status(f"异常：{msg}", state="error")
        self._refresh_button_state()
        QMessageBox.critical(self, "异常", f"采集过程异常：{msg}")

    def _on_cancel(self):
        if self._collecting:
            # 触发 stop_event，worker 在下一轮循环退出
            if self._stop_event is not None:
                self._stop_event.set()
            self._set_status("正在停止...", state="neutral")
            self.cancel_btn.setEnabled(False)
            return
        # 未在采集中 → 直接 reject
        self.reject()

    # ------------------------------------------------------------------
    # 资源释放
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        # 兜底：dialog 关闭时确保 thread 退出 + 摄像头释放
        if self._collecting and self._stop_event is not None:
            self._stop_event.set()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(3000)
        if self._camera_widget is not None:
            self._camera_widget.stop()
        super().closeEvent(event)
