"""
ui/widgets/camera_widget.py — 摄像头预览控件

Phase 2 范围：
- 内部持 cv2.VideoCapture
- QTimer 30 ms 间隔拉帧 → 转 QImage（rgbSwapped）→ 缩放贴 QLabel
- frame_ready 信号上发 BGR ndarray（face_helper 链路消费 BGR）
- start(device_id=0) -> bool，打不开返回 False 并在控件上盖红色"摄像头不可用"
- stop() / capture_one_frame() / closeEvent / __del__ 兜底释放
- 不做人脸框叠加（留给 Phase 5）

Phase 5 增强：
- set_overlay_callback(callable) 注册每帧叠加回调（画人脸框、调试信息等）；
  默认 None，不破坏现有用法。回调签名 (bgr: np.ndarray) -> np.ndarray，
  返回处理后的 BGR（异常会被吞掉，避免中断预览）。

W8 三次审计: _lock 从 bool 改为 threading.Lock (cv2.VideoCapture 不是线程安全,
  FaceCollectDialog worker 在子线程调 capture_one_frame, 主线程 QTimer 也在调)

W12 修复:
- start() 改 MSMF 优先 + 500ms retry + DSHOW fallback (避免 -1072873821 句柄冲突
  + 颜色校准跟 smoke 路径一致)
- 加 pause_preview() 方法 (只停 QTimer, 不 release cap, 让 worker 直读)
- 加 _bgr_to_qimage() 三模式切换 (BGR / RGB / cvt), 配合 Ctrl+R 快捷键实时切换
  (某些 Win11 摄像头驱动色彩字节序不一致, 没法硬编码)
"""
import os
import logging
import threading
from typing import Callable, Optional

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap, QKeyEvent
from PyQt5.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

log = logging.getLogger(__name__)

# W12: 3 种色彩模式 (按 CAMERA_COLOR_MODE 环境变量选, 但实现已统一, 见 _bgr_to_qimage)
COLOR_MODES = ("bgr", "rgb", "cvt")


def cycle_color_mode() -> str:
    """DEPRECATED W12: 循环切换 CAMERA_COLOR_MODE, 返回新模式名 + log.

    之前 UI 学生窗 / 采集 dialog 调, 用来切换 3 模式.
    现在 3 模式实现统一走 cv2.cvtColor (不依赖 PyQt5 内部行为),
    切换无视觉差异 → UI 砍了按钮, 不再调用此函数.

    保留此函数:
    - 给未来调试留口子 (手动设环境变量)
    - 给已部署用户兼容 (旧 .env 设过 CAMERA_COLOR_MODE 不会报错)
    """
    cur = os.getenv("CAMERA_COLOR_MODE", "bgr").lower()
    try:
        idx = COLOR_MODES.index(cur)
    except ValueError:
        idx = 0
    new = COLOR_MODES[(idx + 1) % len(COLOR_MODES)]
    os.environ["CAMERA_COLOR_MODE"] = new
    log.info("W12: CAMERA_COLOR_MODE 切换: %s → %s", cur, new)
    return new


class CameraWidget(QWidget):
    frame_ready = pyqtSignal(np.ndarray)  # BGR frame, shape (H, W, 3)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cap: cv2.VideoCapture | None = None
        self._timer: QTimer | None = None
        # W8 修复: 用 threading.Lock 替代 bool (cv2.VideoCapture 不是线程安全,
        # 主线程 QTimer + 子线程 QThread 都会调 capture_one_frame)
        self._lock = threading.Lock()
        self._overlay_callback: Optional[Callable[[np.ndarray], np.ndarray]] = None
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
        """打开摄像头并开始 30 fps 预览。返回是否成功。

        W12 修复: 优先 MSMF（颜色校准跟 smoke 验证路径一致），加 500ms retry
        处理 -1072873821 句柄冲突，最后 fallback DSHOW。
        DSHOW 优先会导致某些 Win11 摄像头驱动色彩翻转（橙变蓝），
        所以 DSHOW 放最后。
        """
        import time
        if self._cap is not None and self._cap.isOpened():
            return True
        # 顺序: MSMF 0ms -> MSMF 500ms (retry) -> DSHOW 0ms
        backends_with_delay = [
            (cv2.CAP_MSMF, 0),
            (cv2.CAP_MSMF, 500),
            (cv2.CAP_DSHOW, 0),
        ]
        cap = None
        for backend, delay_ms in backends_with_delay:
            if delay_ms > 0:
                time.sleep(delay_ms / 1000)
            try:
                trial = cv2.VideoCapture(device_id, backend)
            except Exception:
                continue
            if not trial.isOpened():
                trial.release()
                continue
            # 验证能真抓一帧（避免 MSMF 句柄冲突导致的"假开"）
            try:
                ok, frame = trial.read()
            except Exception:
                ok, frame = False, None
            if ok and frame is not None and frame.size > 0:
                cap = trial
                break
            trial.release()
        if cap is None:
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

    def pause_preview(self):
        """W12 新增: 只停 preview QTimer, 不 release cap. 让 worker 独占 cap 直读.

        与 stop() 的区别:
        - pause_preview(): 停 QTimer, cap 仍 alive, worker 可用
        - stop(): 停 QTimer + release cap, 完全关闭设备

        用途: face_collect_dialog 复用主窗 CameraWidget 时, _on_start 调
        pause_preview() 让 worker 用 cap, 但关 dialog 时不能 release
        主窗的 cap (主窗还要用).
        """
        if self._timer is not None:
            self._timer.stop()
            self._timer = None
        # cap 保留, label 不动 (worker 还会写 frame_ready 但 QLabel 不再刷新)

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
        与 _on_tick 互斥，避免 cv2.VideoCapture 并发读帧。
        W8 修复: 用 threading.Lock (非 bool) 保证多线程原子.
        W12 修复: 截屏工具触发 DWM 重合成时, cv2 cap.read() 可能抛异常 (MSMF 已知问题).
        全部吞掉 + log, 返 None, 不让 Qt 段错误闪退.
        """
        if self._cap is None or not self._cap.isOpened():
            return None
        if not self._lock.acquire(blocking=False):
            # 别人正在读, 直接返 None (主线程 30ms 后会再来, 子线程下次循环也会再来)
            return None
        try:
            try:
                ok, frame = self._cap.read()
            except Exception as e:
                # W12: 截屏/DWM 抢占导致 cv2 内部状态错乱, 偶发抛异常
                log.warning("cap.read() 异常 (截屏/DWM 抢占常见, 下一帧恢复): %s", e)
                return None
            return frame if ok else None
        finally:
            self._lock.release()

    def request_render(self) -> None:
        """W12 新增: 外部 dialog preview timer 调, 抓一帧 + 渲染到 QLabel.

        等价于内部 _on_tick, 但 public + 不依赖 _timer 是否在跑.
        用 capture_one_frame 走 _lock 互斥, 跟主窗 timer / worker 抢帧不冲突.

        W12 修复: try/except 兜住, 截屏/DWM 抢占导致任何异常都不让 Qt 段错误.
        """
        try:
            frame = self.capture_one_frame()
        except Exception as e:
            log.warning("request_render 抓帧异常: %s", e)
            return
        if frame is None:
            return
        try:
            self._render_frame(frame)
        except Exception as e:
            log.warning("request_render 渲染异常: %s", e)

    def is_running(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def set_overlay_callback(self, callback: Optional[Callable[[np.ndarray], np.ndarray]]) -> None:
        """注册一个每帧叠加回调。返回 BGR ndarray 给预览用。

        异常会被吞掉 + log，避免第三方回调 bug 中断预览主循环。
        传 None 取消叠加。"""
        self._overlay_callback = callback

    def get_cap(self) -> Optional[cv2.VideoCapture]:
        """Phase 5 采集对话框用：拿到底层 cv2.VideoCapture 在子线程里直读，
        避免 CameraWidget 的 bool lock 不是 threading.Lock 的隐患。
        调用方应先 stop() 暂停 preview QTimer 再用。"""
        return self._cap

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
        """W12 修复: try/except 兜住, 截屏/DWM 抢占不闪退."""
        try:
            frame = self.capture_one_frame()
        except Exception as e:
            log.warning("_on_tick 抓帧异常: %s", e)
            return
        if frame is None:
            return
        try:
            self._render_frame(frame)
        except Exception as e:
            log.warning("_on_tick 渲染异常: %s", e)
            return
        try:
            self.frame_ready.emit(frame)
        except Exception as e:
            log.warning("_on_tick frame_ready emit 异常: %s", e)

    def _render_frame(self, bgr: np.ndarray):
        if self._overlay_callback is not None:
            try:
                bgr = self._overlay_callback(bgr)
            except Exception:
                log.exception("overlay_callback 异常（吞掉，避免中断预览）")
        # W12: ndarray shape 异常时 (DWM 抢占偶发) 跳过本帧, 不让 Qt 段错误
        if bgr is None or bgr.ndim != 3 or bgr.shape[2] != 3:
            log.warning("_render_frame 收到异常 ndarray shape=%s, 跳过", getattr(bgr, "shape", None))
            return
        h, w, ch = bgr.shape
        bytes_per_line = ch * w
        try:
            q_img = self._bgr_to_qimage(bgr, bytes_per_line)
            pixmap = QPixmap.fromImage(q_img).scaled(
                self._label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
            self._label.setPixmap(pixmap)
        except Exception as e:
            log.warning("_render_frame QImage/Pixmap 异常: %s", e)

    def _bgr_to_qimage(self, bgr: np.ndarray, bytes_per_line: int) -> QImage:
        """W12 修复: 3 个模式都走 cv2.cvtColor 显式 BGR→RGB.

        历史:
        - v1: bgr/rgb/cvt 三模式各走不同 PyQt5 路径
              → 用户实测 bgr/rgb 显示蓝色 (PyQt5 内部字节解读不可靠)
        - v2 (当前): 三模式都显式 cv2.cvtColor BGR→RGB + Format_RGB888
              → 不依赖 PyQt5 BGR888.rgbSwapped 内部行为, 怎么切都显示橙色

        CAMERA_COLOR_MODE 仍然支持 bgr/rgb/cvt 三选项 (退路兼容),
        但实现统一, 切换不会有视觉差异.
        """
        import os
        # 统一走 cv2 显式 BGR→RGB + .copy() (保险, 不依赖 PyQt5 内部行为)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).copy()
        return QImage(rgb.data, rgb.shape[1], rgb.shape[0],
                      bytes_per_line, QImage.Format_RGB888)

    def _show_unavailable(self):
        self._label.setText("⚠ 摄像头不可用\n请检查摄像头是否被其他程序占用")
        self._label.setStyleSheet(
            "color: #DC2626; background-color: #FEE2E2; "
            "font-size: 14px; padding: 20px;"
        )
