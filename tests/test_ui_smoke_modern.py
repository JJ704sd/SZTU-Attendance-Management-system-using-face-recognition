"""
tests/test_ui_smoke_modern.py — 5 个主窗口启动烟测 (Track 3 验收)

目的: 验证 W14 现代化后 5 个主窗口 (LoginWindow / RegisterWindow /
StudentWindow / TeacherWindow / AdminWindow) 在 offscreen Qt 模式下能
成功 import + 构造 + show() + processEvents() 一次不崩。

策略:
- QT_QPA_PLATFORM=offscreen (CLAUDE.md 警告: Windows + PyQt5 + offscreen
  + QMessageBox 会段错误 → 本测试绝不触发 QMessageBox 按钮, 只调
  __init__ / show() / processEvents()).
- 用 monkeypatch 把 src.db.session_scope 替换成一个 yield MagicMock 的
  上下文管理器, 绕过所有 DB 访问 (不依赖 .env / MySQL).
- FaceService.load_user_encodings mock 成返回空 list, 让学生端
  _refresh_register_status() 不报 DB 错.
- 5 窗口每个用独立 try/finally 包, 一个崩了不影响其他.

注意:
- 这是**构造**测试, 不是业务测试: 不验证人脸识别、不验证签到、不验证
  课程/请假/报表的逻辑; 只验证 "窗口能立起来不崩".
- StudentWindow / TeacherWindow / AdminWindow 都接受 user: User 参数,
  传一个 MagicMock 模拟 user 即可.
- LoginWindow / RegisterWindow 不需要 user 参数, 构造更简单.
- 测试会被 pytest 自动收集 (没有 conftest 跳过规则).
"""
import os
import sys
from contextlib import contextmanager
from unittest.mock import MagicMock

# 强制 offscreen 平台 (CLAUDE.md 警告: Windows + PyQt5 + offscreen +
# QMessageBox 会段错误 → 本测试绝不触发按钮弹窗)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QCoreApplication, QTimer
from PyQt5.QtWidgets import QApplication

from src.ui.styles import apply_global_style


# ============================================================
# Fixtures
# ============================================================
@pytest.fixture(scope="module")
def qapp():
    """QApplication 单例 (offscreen)。"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    apply_global_style(app)
    yield app


@pytest.fixture
def mock_db(monkeypatch):
    """把 src.db.session_scope 替换成 no-op ctx mgr, 绕过所有 DB 访问.

    5 个主窗口在 __init__ 链路里都会调 session_scope() 或
    FaceService.load_user_encodings() 等, 用这个 fixture 一刀切.
    """
    @contextmanager
    def fake_session_scope():
        s = MagicMock()
        try:
            yield s
        finally:
            pass  # 关闭 no-op

    # Patch 所有 import 过 session_scope 的模块
    monkeypatch.setattr("src.db.session_scope", fake_session_scope)

    # 同时 patch 直接引用了 session_scope 的服务 / widget 模块,
    # 避免它们在 __init__ 期间还走旧的 import 路径
    modules_to_patch = [
        "src.services.attendance_service",
        "src.services.face_service",
        "src.services.leave_service",
        "src.services.report_service",
        "src.services.lab_access_service",
        "src.ui.widgets.lab_admin_tab",
        "src.ui.widgets.training_admin_tab",
        "src.ui.widgets.access_log_tab",
        "src.ui.widgets.report_admin_tab",
        "src.ui.widgets.face_admin_tab",
        "src.ui.teacher_window",
        "src.ui.student_window",
    ]
    for mod_name in modules_to_patch:
        try:
            monkeypatch.setattr(f"{mod_name}.session_scope", fake_session_scope)
        except (AttributeError, KeyError):
            pass  # 没 import 这个名字无所谓

    # FaceService.load_user_encodings 返回空 list, 避免学生端 _refresh_register_status() 报
    class FakeFaceService:
        def load_user_encodings(self, user_id):
            return []
        def delete_user_encodings(self, user_id):
            return 0
        def save_encoding(self, *a, **k):
            return None
        def set_primary(self, *a, **k):
            return None
        def collect_for_user(self, *a, **k):
            return 0
        def recognize(self, *a, **k):
            return None

    monkeypatch.setattr("src.services.face_service.FaceService", FakeFaceService)
    # 同样 patch student_window / face_admin_tab 里的引用
    for mod_name in ("src.ui.student_window", "src.ui.widgets.face_admin_tab"):
        try:
            monkeypatch.setattr(f"{mod_name}.FaceService", FakeFaceService)
        except (AttributeError, KeyError):
            pass

    return fake_session_scope


def _make_fake_user(role: str = "student") -> MagicMock:
    """构造一个假 User 对象, 满足主窗口 __init__ 用到的属性."""
    u = MagicMock()
    u.id = 99999
    u.username = f"smoke_{role}"
    u.real_name = f"烟测 {role}"
    u.role = role
    u.student_id = "S000999" if role == "student" else None
    u.email = None
    u.phone = None
    u.is_active = 1
    u.created_at = None
    return u


def _show_and_process(window):
    """show() 一次 + 跑一次 event loop (50ms), 验证 widget tree 渲染不崩."""
    window.show()
    # 不要用 app.exec_() (会卡死); 用 QTimer + processEvents 短脉冲
    QCoreApplication.processEvents()
    QTimer.singleShot(0, lambda: None)
    QCoreApplication.processEvents()


# ============================================================
# Tests
# ============================================================
def test_login_window_constructs(qapp, mock_db):
    """LoginWindow: 不需要 user 参数; 构造 + show() 不崩."""
    from src.ui.login_window import LoginWindow
    w = LoginWindow()
    try:
        _show_and_process(w)
        assert w.isVisible(), "LoginWindow show() 后应可见"
    finally:
        w.close()
        w.deleteLater()


def test_register_window_constructs(qapp, mock_db):
    """RegisterWindow: 不需要 user 参数; 构造 + show() 不崩."""
    from src.ui.register_window import RegisterWindow
    w = RegisterWindow()
    try:
        _show_and_process(w)
        assert w.isVisible(), "RegisterWindow show() 后应可见"
    finally:
        w.close()
        w.deleteLater()


def test_student_window_constructs(qapp, mock_db):
    """StudentWindow: 需要 user; 构造 + show() 不崩; 4 Tab 全部建立."""
    from src.ui.student_window import StudentWindow
    user = _make_fake_user("student")
    w = StudentWindow(user)
    try:
        _show_and_process(w)
        assert w.isVisible(), "StudentWindow show() 后应可见"
        # Tab widget 存在且有 4 个 Tab (注册/签到/我的考勤/我的请假)
        assert w.tabs.count() == 4, (
            f"StudentWindow 期望 4 Tab, 实际 {w.tabs.count()}"
        )
    finally:
        w.close()
        w.deleteLater()


def test_teacher_window_constructs(qapp, mock_db):
    """TeacherWindow: 需要 user; 构造 + show() 不崩; 4 Tab 全部建立."""
    from src.ui.teacher_window import TeacherWindow
    user = _make_fake_user("teacher")
    w = TeacherWindow(user)
    try:
        _show_and_process(w)
        assert w.isVisible(), "TeacherWindow show() 后应可见"
        assert w.tabs.count() == 4, (
            f"TeacherWindow 期望 4 Tab, 实际 {w.tabs.count()}"
        )
    finally:
        w.close()
        w.deleteLater()


def test_admin_window_constructs(qapp, mock_db):
    """AdminWindow: 需要 user; 构造 + show() 不崩; 5 Tab 全部建立."""
    from src.ui.admin_window import AdminWindow
    user = _make_fake_user("lab_admin")
    w = AdminWindow(user)
    try:
        _show_and_process(w)
        assert w.isVisible(), "AdminWindow show() 后应可见"
        assert w.tabs.count() == 5, (
            f"AdminWindow 期望 5 Tab, 实际 {w.tabs.count()}"
        )
    finally:
        w.close()
        w.deleteLater()


# ============================================================
# 风格 / 现代化 验收
# ============================================================
def test_all_windows_have_modernized_resize(qapp, mock_db):
    """5 窗口的 W14 现代化尺寸生效 (login 460x540 / register 520x660 /
    student 960x680 / teacher 960x640 / admin 1140x740)."""
    from src.ui.login_window import LoginWindow
    from src.ui.register_window import RegisterWindow
    from src.ui.student_window import StudentWindow
    from src.ui.teacher_window import TeacherWindow
    from src.ui.admin_window import AdminWindow

    checks = [
        (LoginWindow(), 460, 540),
        (RegisterWindow(), 520, 660),
        (StudentWindow(_make_fake_user("student")), 960, 680),
        (TeacherWindow(_make_fake_user("teacher")), 960, 640),
        (AdminWindow(_make_fake_user("lab_admin")), 1140, 740),
    ]
    try:
        for w, w_w, w_h in checks:
            actual = (w.width(), w.height())
            assert actual == (w_w, w_h), (
                f"{type(w).__name__} 期望 ({w_w},{w_h}), 实际 {actual}"
            )
    finally:
        for w, _, _ in checks:
            w.close()
            w.deleteLater()


def test_student_teacher_tables_have_alternating_row_colors(qapp, mock_db):
    """StudentWindow attendance_table / leave_table + TeacherWindow
    history_table 都已 setAlternatingRowColors(True)."""
    from src.ui.student_window import StudentWindow
    from src.ui.teacher_window import TeacherWindow

    sw = StudentWindow(_make_fake_user("student"))
    tw = TeacherWindow(_make_fake_user("teacher"))
    try:
        assert sw.attendance_table.alternatingRowColors(), (
            "StudentWindow.attendance_table 应开启斑马纹"
        )
        assert sw.leave_table.alternatingRowColors(), (
            "StudentWindow.leave_table 应开启斑马纹"
        )
        assert tw.history_table.alternatingRowColors(), (
            "TeacherWindow.history_table 应开启斑马纹"
        )
    finally:
        for w in (sw, tw):
            w.close()
            w.deleteLater()
