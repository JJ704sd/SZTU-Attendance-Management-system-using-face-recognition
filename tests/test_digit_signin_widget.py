"""
tests/test_digit_signin_widget.py — DigitSigninWidget 构造 smoke

W13+ 学生端「数字码签到」子 Tab。
仅验证 import + offscreen Qt 模式构造 widget + 属性挂上 + signal 存在。
不触发 sign_in_by_digit（避免真 DB）。
"""
import os

# 强制 offscreen (CLAUDE.md 警告)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QWidget, QLineEdit, QPushButton, QLabel


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app


def test_digit_signin_widget_constructs(qapp):
    """构造数字码签到 widget 不抛 + 关键属性挂上。"""
    from src.ui.widgets.digit_signin_widget import DigitSigninWidget
    fake_svc = object()  # 传一个 mock；__init__ 不调 service 方法
    w = DigitSigninWidget(parent=None, task_id=1, user_id=2, attendance_service=fake_svc)
    try:
        assert isinstance(w, QWidget)
        # 关键属性
        assert w._task_id == 1
        assert w._user_id == 2
        assert w._attendance_service is fake_svc
        # UI 元素
        assert hasattr(w, "code_edit") and isinstance(w.code_edit, QLineEdit)
        assert hasattr(w, "submit_btn") and isinstance(w.submit_btn, QPushButton)
        assert hasattr(w, "status_label") and isinstance(w.status_label, QLabel)
        # QLineEdit 限制 4 位 + 数字
        assert w.code_edit.maxLength() == 4, \
            f"QLineEdit 应 maxLength=4, 实际 {w.code_edit.maxLength()}"
        # signal 存在
        assert hasattr(w, "signin_succeeded"), "missing signin_succeeded signal"
    finally:
        w.close()
        w.deleteLater()


def test_digit_signin_widget_does_not_call_service_on_init(qapp):
    """构造时不应调 sign_in_by_digit（避免真 DB）。"""
    from src.ui.widgets.digit_signin_widget import DigitSigninWidget

    class SpyService:
        def __init__(self):
            self.sign_in_by_digit_called = False
        def sign_in_by_digit(self, *a, **k):
            self.sign_in_by_digit_called = True
            return None

    spy = SpyService()
    w = DigitSigninWidget(parent=None, task_id=1, user_id=2, attendance_service=spy)
    try:
        assert spy.sign_in_by_digit_called is False, \
            "构造时不应调 sign_in_by_digit"
    finally:
        w.close()
        w.deleteLater()
