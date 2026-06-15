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
