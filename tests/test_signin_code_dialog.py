"""
tests/test_signin_code_dialog.py — SigninCodeDialog 构造 smoke

W13+ 教师端签到码显示弹窗（数字码 / 二维码共用）。
仅验证 import + 在 offscreen Qt 模式下能成功构造 widget + 属性挂上。

⚠️ 不要在 offscreen 模式下触发 QMessageBox（CLAUDE.md 警告段错误）。
   也不在 __init__ 走真 DB 路径：用 monkey-patch 把 AttendanceService 的
   __init__ / generate_signin_code / QMessageBox.warning 替换为 no-op。
"""
import os

# 强制 offscreen (CLAUDE.md 警告)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtWidgets import QApplication, QDialog


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app


@pytest.fixture
def patched_service(monkeypatch):
    """Mock AttendanceService，避免 __init__ 走 DB / 不弹 QMessageBox。

    ⚠️ 当前 worktree 的 AttendanceService 没有 generate_signin_code（W13+
    改造尚未合入），所以先 monkey-patch __init__ 跳过真 DB，再用 setattr
    把 generate_signin_code 加上去。
    """
    from src.ui.widgets import signin_code_dialog as scd_mod

    def fake_init(self):
        pass  # 跳过 AttendanceService 真实 __init__

    def fake_generate(self, task_id, code_type, ttl_seconds=60):
        return None  # 让 widget 的 _generate_code 走 close 分支（no-op）

    monkeypatch.setattr(scd_mod.AttendanceService, "__init__", fake_init)
    # 类可能没有该属性，先 setattr（创建），monkeypatch 会负责 teardown 还原
    scd_mod.AttendanceService.generate_signin_code = fake_generate
    # 用 monkeypatch.delattr 还原（如果原本没有就 AttributeError catch 住）
    monkeypatch.setattr(
        scd_mod.QMessageBox, "warning",
        staticmethod(lambda *a, **k: None),
    )
    yield scd_mod
    # 兜底清理（如果 monkeypatch 没自动还原的话）
    if not hasattr(scd_mod.AttendanceService, "generate_signin_code") or \
       scd_mod.AttendanceService.generate_signin_code is fake_generate:
        # 类原本没有 → 删除
        try:
            del scd_mod.AttendanceService.generate_signin_code
        except AttributeError:
            pass


def test_signin_code_dialog_digit_constructs(qapp, patched_service):
    """构造数字码弹窗不抛 + 属性挂上。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    dlg = SigninCodeDialog(parent=None, task_id=1, code_type="digit")
    try:
        assert isinstance(dlg, QDialog)
        assert dlg.task_id == 1
        assert dlg.code_type == "digit"
        # 关键属性
        for attr in ("_code_value", "_expires_at", "_timer",
                     "refresh_btn", "close_btn", "code_label", "progress_bar"):
            assert hasattr(dlg, attr), f"missing attr {attr}"
    finally:
        dlg.close()
        dlg.deleteLater()


def test_signin_code_dialog_qr_constructs(qapp, patched_service):
    """构造二维码弹窗不抛。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    dlg = SigninCodeDialog(parent=None, task_id=2, code_type="qr")
    try:
        assert isinstance(dlg, QDialog)
        assert dlg.task_id == 2
        assert dlg.code_type == "qr"
    finally:
        dlg.close()
        dlg.deleteLater()


def test_signin_code_dialog_invalid_type_raises(qapp, patched_service):
    """无效 code_type 应抛 ValueError。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    with pytest.raises(ValueError):
        SigninCodeDialog(parent=None, task_id=1, code_type="xxx")
