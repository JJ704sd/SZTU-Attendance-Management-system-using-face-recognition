"""
tests/test_qr_scan_widget.py — QrScanWidget 构造 smoke

W13+ 学生端「二维码扫描签到」子 Tab。
仅验证 import + offscreen Qt 模式构造 widget + 属性挂上 + signal 存在。
不触发摄像头启动（避免无相机设备失败）和真 DB sign_in_by_qr。
"""
import os

# 强制 offscreen (CLAUDE.md 警告)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QPushButton


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app


def test_qr_scan_widget_constructs(qapp):
    """构造二维码扫描 widget 不抛 + 关键属性挂上。"""
    from src.ui.widgets.qr_scan_widget import QrScanWidget
    fake_svc = object()
    w = QrScanWidget(parent=None, task_id=1, user_id=2, attendance_service=fake_svc)
    try:
        assert isinstance(w, QWidget)
        # 关键属性
        assert w._task_id == 1
        assert w._user_id == 2
        assert w._attendance_service is fake_svc
        assert w._scanning is False
        # UI 元素
        assert hasattr(w, "camera")
        assert hasattr(w, "status_label") and isinstance(w.status_label, QLabel)
        assert hasattr(w, "open_cam_btn") and isinstance(w.open_cam_btn, QPushButton)
        assert hasattr(w, "start_scan_btn") and isinstance(w.start_scan_btn, QPushButton)
        assert hasattr(w, "stop_scan_btn") and isinstance(w.stop_scan_btn, QPushButton)
        # timer 存在但未启动
        assert isinstance(w._scan_timer, QTimer)
        assert not w._scan_timer.isActive(), "构造时 scan timer 不应启动"
        # signal
        assert hasattr(w, "signin_succeeded")
    finally:
        w.close()
        w.deleteLater()


def test_qr_scan_widget_does_not_call_service_on_init(qapp):
    """构造时不应调 sign_in_by_qr（避免真 DB）。"""
    from src.ui.widgets.qr_scan_widget import QrScanWidget

    class SpyService:
        def __init__(self):
            self.sign_in_by_qr_called = False
        def sign_in_by_qr(self, *a, **k):
            self.sign_in_by_qr_called = True
            return None

    spy = SpyService()
    w = QrScanWidget(parent=None, task_id=1, user_id=2, attendance_service=spy)
    try:
        assert spy.sign_in_by_qr_called is False
    finally:
        w.close()
        w.deleteLater()


# =============================================================================
# R16: 公开 API cleanup_for_parent_close —— 父窗口 close 时的清理契约
# =============================================================================
def test_qr_scan_widget_has_cleanup_for_parent_close_api(qapp):
    """R16: QrScanWidget 暴露 cleanup_for_parent_close 公开 API.

    动机: 旧版 StudentWindow._cleanup_resources 直接碰 QrScanWidget 的
    私有方法 _stop_scan_internal() 和 .camera 属性, 破坏封装.
    R16 引入公开 API, 父 widget 走契约即可, 不依赖私有细节.
    """
    from src.ui.widgets.qr_scan_widget import QrScanWidget
    w = QrScanWidget(parent=None, task_id=1, user_id=2, attendance_service=object())
    try:
        assert hasattr(w, "cleanup_for_parent_close"), (
            "QrScanWidget 应暴露 cleanup_for_parent_close 公开 API (R16 修复)"
        )
        assert callable(getattr(w, "cleanup_for_parent_close")), (
            "cleanup_for_parent_close 应是可调用的方法"
        )
    finally:
        w.close()
        w.deleteLater()


def test_qr_scan_widget_cleanup_for_parent_close_stops_scan_timer(qapp):
    """R16: cleanup_for_parent_close 在扫描中调用 → 停 scan timer.

    验证流程:
    1) mock camera.is_running() = True, _scanning = True, _scan_timer 启
    2) 调 cleanup_for_parent_close()
    3) 期望: _scan_timer.stop() 被调, _scanning = False
    """
    from unittest.mock import MagicMock, patch
    from src.ui.widgets.qr_scan_widget import QrScanWidget

    w = QrScanWidget(parent=None, task_id=1, user_id=2, attendance_service=object())
    try:
        # mock camera 让 is_running 返 True, stop 是 spy
        w.camera = MagicMock()
        w.camera.is_running.return_value = True
        stop_spy = MagicMock()
        w.camera.stop = stop_spy

        # 模拟"扫描中"状态
        w._scanning = True
        w._scan_timer.start()

        assert w._scan_timer.isActive(), "前置: scan timer 应已启"

        # 调公开 API
        w.cleanup_for_parent_close()

        # 期望: _scanning 复位, timer 停, camera.stop 被调
        assert w._scanning is False, "清理后 _scanning 应复位"
        assert not w._scan_timer.isActive(), "清理后 scan timer 应停"
        stop_spy.assert_called_once(), "camera.stop 应被调一次"
    finally:
        w.close()
        w.deleteLater()


def test_qr_scan_widget_cleanup_for_parent_close_is_idempotent(qapp):
    """R16: cleanup_for_parent_close 可重入 —— 多次调用不抛.

    边界: camera 已 stop / scan 已停 时再调, 应是 no-op, 不抛异常.
    """
    from unittest.mock import MagicMock
    from src.ui.widgets.qr_scan_widget import QrScanWidget

    w = QrScanWidget(parent=None, task_id=1, user_id=2, attendance_service=object())
    try:
        # camera 不在跑 (默认状态)
        w.camera = MagicMock()
        w.camera.is_running.return_value = False

        # 多次调不应抛
        for _ in range(3):
            w.cleanup_for_parent_close()

        # 第二次起 camera.stop 不该再被调 (is_running 返 False)
        assert w.camera.stop.call_count == 0, (
            "camera 未启动时 cleanup 不应调 stop"
        )
    finally:
        w.close()
        w.deleteLater()


def test_qr_scan_widget_cleanup_swallows_camera_exceptions(qapp):
    """R16: cleanup_for_parent_close 吞掉 camera.stop 抛的异常.

    防御: 父窗口关闭流程不应被子 widget 异常打断 (CLAUDE.md 教学案例).
    """
    from unittest.mock import MagicMock
    from src.ui.widgets.qr_scan_widget import QrScanWidget

    w = QrScanWidget(parent=None, task_id=1, user_id=2, attendance_service=object())
    try:
        w.camera = MagicMock()
        w.camera.is_running.return_value = True
        w.camera.stop.side_effect = RuntimeError("cv2 释放异常")

        # 不应向上抛
        try:
            w.cleanup_for_parent_close()
        except RuntimeError as e:
            pytest.fail(f"cleanup_for_parent_close 不应向外抛 camera.stop 异常: {e}")
    finally:
        w.close()
        w.deleteLater()
