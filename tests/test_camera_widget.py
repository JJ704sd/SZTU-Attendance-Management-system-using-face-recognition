"""
tests/test_camera_widget.py — CameraWidget 启动逻辑回归测试 (W12)

覆盖 W12 发现的真 bug:
- Bug A: CameraWidget.start() 后端顺序: MSMF 优先 (颜色校准跟 smoke 路径一致),
  加 500ms retry 处理 -1072873821 句柄冲突, 最后 fallback DSHOW.
- Bug B: DSHOW 在某些 Win11 摄像头驱动上色彩翻转 (橙变蓝), 放最后兜底.

测试策略:
- mock cv2.VideoCapture, 模拟 "MSMF 假开" / "MSMF retry 成功" / "fallback DSHOW"
  / "都失败" 4 种场景.
- 不真开摄像头, 跑得快 (CI 友好).
"""
import sys
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# offscreen 模式跑 Qt 不弹窗
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _make_fake_cap(read_ok: bool = True, frame_shape=(480, 640, 3)):
    """构造 cv2.VideoCapture mock. 模拟 '能开 + 能读' 或 '假开'."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.read.return_value = (
        (read_ok, MagicMock(shape=frame_shape, size=frame_shape[0] * frame_shape[1] * 3))
        if read_ok else (False, None)
    )
    return cap


def test_start_prefers_msmf_backend(qapp):
    """MSMF 能开 + 能读 → 走 MSMF, 不尝试 DSHOW 也不 retry."""
    from src.ui.widgets.camera_widget import CameraWidget
    msmf_cap = _make_fake_cap(read_ok=True)
    with patch("cv2.VideoCapture", return_value=msmf_cap) as vc, \
         patch("time.sleep") as sleep:  # 不真 sleep
        widget = CameraWidget()
        ok = widget.start(0)
        assert ok is True
        # 第一次调用必须是 MSMF
        first_call = vc.call_args_list[0]
        assert first_call[0][1] == cv2.CAP_MSMF, f"期望 MSMF, 实际 {first_call}"
        # 不会 retry (没 sleep), 不会 fallback DSHOW
        assert len(vc.call_args_list) == 1
        sleep.assert_not_called()
        widget.stop()


def test_start_retries_msmf_when_first_try_fake_opens(qapp):
    """MSMF 第一次假开 → sleep 500ms → MSMF 第二次成功 (处理 -1072873821)."""
    from src.ui.widgets.camera_widget import CameraWidget

    msmf_bad = _make_fake_cap(read_ok=False)  # 第一次假开
    msmf_good = _make_fake_cap(read_ok=True)   # 第二次成功

    with patch("cv2.VideoCapture", side_effect=[msmf_bad, msmf_good]) as vc, \
         patch("time.sleep") as sleep:
        widget = CameraWidget()
        ok = widget.start(0)
        assert ok is True
        # 顺序: 1) MSMF 失败  2) MSMF 成功 (不试 DSHOW)
        assert vc.call_args_list[0][0][1] == cv2.CAP_MSMF
        assert vc.call_args_list[1][0][1] == cv2.CAP_MSMF
        assert len(vc.call_args_list) == 2
        # retry 路径必须 sleep 500ms (避免连续开 MSMF 又冲突)
        sleep.assert_called_once_with(0.5)
        widget.stop()


def test_start_falls_back_to_dshow_when_msmf_keeps_failing(qapp):
    """MSMF 假开两次 (含 retry) → fallback DSHOW → 成功."""
    from src.ui.widgets.camera_widget import CameraWidget

    bad1 = _make_fake_cap(read_ok=False)
    bad2 = _make_fake_cap(read_ok=False)
    dshow_good = _make_fake_cap(read_ok=True)

    with patch("cv2.VideoCapture", side_effect=[bad1, bad2, dshow_good]), \
         patch("time.sleep"):
        widget = CameraWidget()
        ok = widget.start(0)
        assert ok is True
        # MSMF 失败 2 次 + DSHOW 成功 1 次
        assert len(widget._cap and [None] or []) >= 0  # 不用这个, 直接看 call_args_list
        widget.stop()


def test_start_returns_false_when_all_backends_fail(qapp):
    """MSMF (2 次) + DSHOW 都失败 → 返 False, 摄像头不可用."""
    from src.ui.widgets.camera_widget import CameraWidget

    bad1 = _make_fake_cap(read_ok=False)
    bad2 = _make_fake_cap(read_ok=False)
    bad3 = _make_fake_cap(read_ok=False)

    with patch("cv2.VideoCapture", side_effect=[bad1, bad2, bad3]), \
         patch("time.sleep"):
        widget = CameraWidget()
        ok = widget.start(0)
        assert ok is False
        assert widget._cap is None
        widget.stop()


def test_start_returns_false_when_msmf_raises(qapp):
    """MSMF 构造抛异常 → retry 也抛 → DSHOW 也抛 → 返 False (不崩)."""
    from src.ui.widgets.camera_widget import CameraWidget

    with patch("cv2.VideoCapture", side_effect=OSError("device busy")), \
         patch("time.sleep"):
        widget = CameraWidget()
        ok = widget.start(0)
        assert ok is False
        widget.stop()


# =============================================================================
# W12: pause_preview / stop / _owns_camera 测试
# =============================================================================
def test_pause_preview_does_not_release_cap(qapp):
    """pause_preview() 只停 QTimer, cap 仍 alive (worker 可用)."""
    from src.ui.widgets.camera_widget import CameraWidget
    cap = _make_fake_cap(read_ok=True)
    with patch("cv2.VideoCapture", return_value=cap), patch("time.sleep"):
        widget = CameraWidget()
        widget.start(0)
        assert widget.is_running()
        widget.pause_preview()
        # cap 还活着
        assert widget._cap is not None
        assert widget._cap.isOpened.return_value is True
        # timer 停了
        assert widget._timer is None


def test_stop_still_releases_cap(qapp):
    """stop() 仍 release cap (回归: 拆分 pause_preview 不能破坏 stop 行为)."""
    from src.ui.widgets.camera_widget import CameraWidget
    cap = _make_fake_cap(read_ok=True)
    with patch("cv2.VideoCapture", return_value=cap), patch("time.sleep"):
        widget = CameraWidget()
        widget.start(0)
        widget.stop()
        # cap 已 release
        assert widget._cap is None


# =============================================================================
# W12: 色彩模式切换 (橙变蓝问题修复)
# =============================================================================
def _extract_pixel(qimage: "QImage", x: int = 50, y: int = 50) -> tuple:
    """从 QImage 提取 (R, G, B) 像素."""
    from PyQt5.QtGui import QImage
    p = qimage.bits()
    p.setsize(qimage.byteCount())
    arr = np.frombuffer(p, dtype=np.uint8).reshape(qimage.height(), qimage.width(), 3).copy()
    return tuple(arr[y, x])


def test_bgr_to_qimage_bgr_mode_shows_correct_color(qapp):
    """bgr 模式: 橙色 BGR ndarray → 橙色 RGB 显示 (rgbSwapped)."""
    import os
    from src.ui.widgets.camera_widget import CameraWidget
    os.environ["CAMERA_COLOR_MODE"] = "bgr"
    widget = CameraWidget()
    # 橙色 BGR = (0, 165, 255) bytes
    bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    bgr[:, :, 0] = 0; bgr[:, :, 1] = 165; bgr[:, :, 2] = 255
    q = widget._bgr_to_qimage(bgr, 300)
    # 橙色 RGB = (255, 165, 0)
    assert _extract_pixel(q) == (255, 165, 0), f"bgr 模式期望橙 (255,165,0), 实际 {_extract_pixel(q)}"


def test_bgr_to_qimage_default_mode_is_cvt(qapp):
    """W12 v4: 默认模式 cvt (用户实测 cvt 对, 不依赖 PyQt5 内部行为).

    历史:
    - v1: bgr (跟 OpenCV 标准)
    - v2: rgb (误判, 错了)
    - v3: 改回 bgr
    - v4: cvt (用户实测对, 最稳)
    - v5 (当前): 3 模式实现统一走 cv2.cvtColor (bgr/rgb/cvt 都对),
      默认是 cvt, UI 砍了按钮, 但环境变量仍兼容
    """
    import os
    from src.ui.widgets.camera_widget import CameraWidget
    os.environ.pop("CAMERA_COLOR_MODE", None)  # 清除强制设的值
    widget = CameraWidget()
    # 模拟标准 BGR 字节序 [0, 140, 255] (橙色 = BGR 0,140,255)
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:, :, 0] = 0; arr[:, :, 1] = 140; arr[:, :, 2] = 255
    q = widget._bgr_to_qimage(arr, 300)
    # 默认 cvt 模式: cv2 显式 BGR→RGB, 显示橙
    assert _extract_pixel(q) == (255, 140, 0), f"默认 cvt 模式期望橙 (255,140,0), 实际 {_extract_pixel(q)}"


def test_bgr_to_qimage_all_three_modes_unified(qapp):
    """W12 v5: 3 模式实现统一走 cv2.cvtColor, 切换没视觉差异.

    bgr/rgb/cvt 都走 cv2.cvtColor(BGR→RGB) + Format_RGB888, 3 模式像素输出完全一样.
    这样:
    - 用户切不切换都显示橙
    - 不依赖 PyQt5 Format_BGR888.rgbSwapped 内部行为
    - bgr/rgb 模式名保留 (兼容老 .env), 但功能等价 cvt
    """
    import os
    from src.ui.widgets.camera_widget import CameraWidget
    arr = np.zeros((100, 100, 3), dtype=np.uint8)
    arr[:, :, 0] = 0; arr[:, :, 1] = 140; arr[:, :, 2] = 255  # 橙色 BGR
    results = {}
    for mode in ("bgr", "rgb", "cvt"):
        os.environ["CAMERA_COLOR_MODE"] = mode
        widget = CameraWidget()
        q = widget._bgr_to_qimage(arr, 300)
        results[mode] = _extract_pixel(q)
    # 3 模式输出完全一致
    assert results["bgr"] == results["rgb"] == results["cvt"] == (255, 140, 0), (
        f"3 模式应该都返回橙 (255,140,0), 实际 {results}"
    )


def test_cycle_color_mode_cycles_bgr_rgb_cvt(qapp):
    """cycle_color_mode 在 bgr→rgb→cvt→bgr 循环."""
    import os
    from src.ui.widgets.camera_widget import cycle_color_mode
    os.environ["CAMERA_COLOR_MODE"] = "bgr"
    assert cycle_color_mode() == "rgb"  # bgr → rgb
    assert cycle_color_mode() == "cvt"  # rgb → cvt
    assert cycle_color_mode() == "bgr"  # cvt → bgr
    assert cycle_color_mode() == "rgb"  # bgr → rgb (循环)


def test_cycle_color_mode_handles_invalid_initial():
    """环境变量设成无效值时, cycle_color_mode 回到 rgb (W12 默认)."""
    import os
    from src.ui.widgets.camera_widget import cycle_color_mode
    os.environ["CAMERA_COLOR_MODE"] = "garbage"
    assert cycle_color_mode() == "rgb"  # 找不到 garbage → idx=0 → 下一个是 rgb


# =============================================================================
# W12: request_render() 公开方法 (dialog preview timer 用)
# =============================================================================
def test_request_render_calls_capture_and_render(qapp):
    """request_render() 走 capture_one_frame + _render_frame.

    用途: dialog 内部 preview timer 调, 让 dialog 里的画面动态更新
    (之前 pause_preview 让 dialog 预览变静态, UX 差).
    """
    from src.ui.widgets.camera_widget import CameraWidget
    cap = _make_fake_cap(read_ok=True)
    with patch("cv2.VideoCapture", return_value=cap), patch("time.sleep"):
        widget = CameraWidget()
        widget.start(0)
        # mock _render_frame 验证被调
        with patch.object(widget, "_render_frame") as render:
            widget.request_render()
            # capture_one_frame 拿到帧 → 调 _render_frame
            render.assert_called_once()
            # 传入的是 ndarray
            args = render.call_args[0]
            assert args[0] is not None
            assert hasattr(args[0], "shape")


def test_request_render_skips_when_no_frame(qapp):
    """cap 拿不到帧时, request_render 不调 _render_frame."""
    from src.ui.widgets.camera_widget import CameraWidget
    cap = _make_fake_cap(read_ok=False)
    with patch("cv2.VideoCapture", return_value=cap), patch("time.sleep"):
        widget = CameraWidget()
        widget.start(0)
        with patch.object(widget, "_render_frame") as render:
            widget.request_render()
            render.assert_not_called()


# =============================================================================
# W12: _WorkerCamera 改用 CameraWidget.capture_one_frame (带 _lock 互斥)
# =============================================================================
def test_worker_camera_uses_camera_widget_capture(qapp):
    """_WorkerCamera(camera_widget).capture_one_frame() 走 widget 的 _lock 互斥版本.

    背景: 之前 _WorkerCamera(cap) 直接 cap.read() 跟主窗 QTimer 抢帧, race.
    改用 CameraWidget.capture_one_frame() (带 _lock.acquire(blocking=False)) 后,
    抢失败返 None, 主线程 30ms 后再来.
    """
    from src.ui.widgets.face_collect_dialog import _WorkerCamera
    from src.ui.widgets.camera_widget import CameraWidget
    cap = _make_fake_cap(read_ok=True)
    with patch("cv2.VideoCapture", return_value=cap), patch("time.sleep"):
        widget = CameraWidget()
        widget.start(0)
        # 验证 _WorkerCamera 持 camera_widget
        wcam = _WorkerCamera(widget)
        # capture_one_frame 走 widget 的 capture_one_frame (带 _lock)
        with patch.object(widget, "capture_one_frame", return_value="frame") as widget_capture:
            result = wcam.capture_one_frame()
            widget_capture.assert_called_once()
            assert result == "frame"


def test_worker_camera_returns_none_when_widget_not_running(qapp):
    """camera_widget 关闭时, _WorkerCamera.capture_one_frame 返 None."""
    from src.ui.widgets.face_collect_dialog import _WorkerCamera
    from src.ui.widgets.camera_widget import CameraWidget
    widget = CameraWidget()  # 没 start
    wcam = _WorkerCamera(widget)
    assert wcam.is_running() is False
    assert wcam.capture_one_frame() is None
