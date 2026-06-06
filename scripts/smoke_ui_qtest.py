"""
scripts/smoke_ui_qtest.py — QTest 真实 UI 交互 (W6 Phase 4)

用 PyQt5.QtTest 模拟用户操作:
  1. 启 LoginWindow (offscreen)
  2. QTest.keyClicks 输用户名 + 密码
  3. QTest.mouseClick 登录按钮
  4. 验证 next_win (Teacher / Admin / StudentWindow) 被正确创建
  5. 切 Tab (QTabWidget)
  6. 切 chart combo (QComboBox) - 验证不挂

⚠️ offscreen 模式 + QMessageBox 模态会 hang, 脚本会 monkey-patch
QMessageBox.* 静默 (真用户使用时模态弹窗正常).

用法:
  .venv\Scripts\python.exe scripts\smoke_ui_qtest.py

退出码: 0=PASS / 1=FAIL
"""
import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 强制 offscreen
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Monkey-patch QMessageBox 避免模态 hang
import PyQt5.QtWidgets as qtw
_orig_information = qtw.QMessageBox.information
_orig_warning = qtw.QMessageBox.warning
_orig_critical = qtw.QMessageBox.critical
_orig_question = qtw.QMessageBox.question
qtw.QMessageBox.information = staticmethod(lambda *a, **k: qtw.QMessageBox.Ok)
qtw.QMessageBox.warning = staticmethod(lambda *a, **k: qtw.QMessageBox.Ok)
qtw.QMessageBox.critical = staticmethod(lambda *a, **k: qtw.QMessageBox.Ok)
qtw.QMessageBox.question = staticmethod(lambda *a, **k: qtw.QMessageBox.Yes)

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest

from src.db import session_scope
from src.models.user import User
from src.services.auth_service import AuthService
from src.ui.login_window import LoginWindow


def _section(t: str):
    print(f"\n=== {t} ===", flush=True)


def _ok(m: str):
    print(f"  [OK] {m}", flush=True)


def _fail(m: str):
    print(f"  [FAIL] {m}", flush=True)


def _login_via_ui(username: str, password: str, role_label: str) -> object:
    """用 QTest 模拟登录, 返回 next_win (Teacher / Admin / StudentWindow).

    role_label: '学生' / '教师' / '实验室管理员' (匹配下拉显示文字)
    """
    win = LoginWindow()
    win.show()
    # 选角色 (按显示文字)
    target_idx = -1
    for i in range(win.role_combo.count()):
        if win.role_combo.itemText(i) == role_label:
            target_idx = i
            break
    if target_idx < 0:
        _fail(f"role_combo 找不到 '{role_label}'")
        return None
    win.role_combo.setCurrentIndex(target_idx)
    # keyClicks: 先点用户名框 + 输入
    QTest.mouseClick(win.username_edit, Qt.LeftButton)
    QTest.keyClicks(win.username_edit, username)
    # 然后点密码框 + 输入
    QTest.mouseClick(win.password_edit, Qt.LeftButton)
    QTest.keyClicks(win.password_edit, password)
    # 点登录按钮
    QTest.mouseClick(win.login_btn, Qt.LeftButton)
    QTest.qWait(300)  # 给信号槽一点时间
    return win.next_win if hasattr(win, "next_win") and win.next_win else None


def main() -> int:
    # 启 QApplication
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    suf = uuid.uuid4().hex[:6]

    # ====================================================
    # 1. 准备 3 个测试账号
    # ====================================================
    _section("1. 准备 3 角色账号")
    try:
        auth = AuthService()
        admin = auth.register(
            username=f"smk_qt_a_{suf}", password="123456",
            real_name="QTest 管理员", role="lab_admin",
        )
        teacher = auth.register(
            username=f"smk_qt_t_{suf}", password="123456",
            real_name="QTest 老师", role="teacher",
        )
        student = auth.register(
            username=f"smk_qt_s_{suf}", password="123456",
            real_name="QTest 学生", role="student",
            student_id=f"QTS{suf}",
        )
        _ok(f"3 角色账号: admin={admin.id} teacher={teacher.id} student={student.id}")
    except Exception as e:
        _fail(f"准备失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 2. 学生登录 → 切 Tab
    # ====================================================
    _section("2. 学生登录 (QTest 键入 + 按钮点击)")
    try:
        # 关闭可能残留的窗口
        QTest.qWait(100)
        next_win = _login_via_ui(
            username=student.username, password="123456", role_label="学生",
        )
        if next_win is None:
            _fail("学生登录后 next_win 没创建")
            return 1
        _ok(f"学生登录成功: {type(next_win).__name__}, title='{next_win.windowTitle()}'")
        # 验证 4 Tab 都能切
        from src.ui.student_window import StudentWindow
        assert isinstance(next_win, StudentWindow), f"应该是 StudentWindow, 实际 {type(next_win).__name__}"
        for i in range(4):
            next_win.tabs.setCurrentIndex(i)
            QTest.qWait(50)
            _ok(f"  学生 Tab {i} '{next_win.tabs.tabText(i)}' 切换 OK")
        next_win.close()
        QTest.qWait(100)
    except Exception as e:
        _fail(f"学生登录 + Tab 切换失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 3. 教师登录 → 切 Tab
    # ====================================================
    _section("3. 教师登录 + 切 Tab")
    try:
        next_win = _login_via_ui(
            username=teacher.username, password="123456", role_label="教师",
        )
        if next_win is None:
            _fail("教师登录后 next_win 没创建")
            return 1
        _ok(f"教师登录成功: {type(next_win).__name__}")
        from src.ui.teacher_window import TeacherWindow
        assert isinstance(next_win, TeacherWindow)
        for i in range(4):
            next_win.tabs.setCurrentIndex(i)
            QTest.qWait(50)
            _ok(f"  教师 Tab {i} '{next_win.tabs.tabText(i)}' 切换 OK")
        next_win.close()
        QTest.qWait(100)
    except Exception as e:
        _fail(f"教师登录 + Tab 切换失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 4. 管理员登录 → 切 Tab + 切 4 chart
    # ====================================================
    _section("4. 管理员登录 + 切 Tab + 切 4 chart")
    try:
        next_win = _login_via_ui(
            username=admin.username, password="123456", role_label="实验室管理员",
        )
        if next_win is None:
            _fail("管理员登录后 next_win 没创建")
            return 1
        _ok(f"管理员登录成功: {type(next_win).__name__}")
        from src.ui.admin_window import AdminWindow
        assert isinstance(next_win, AdminWindow)
        for i in range(4):
            next_win.tabs.setCurrentIndex(i)
            QTest.qWait(50)
            _ok(f"  admin Tab {i} '{next_win.tabs.tabText(i)}' 切换 OK")
        # 切到 Tab 3 (使用率报表) 验 4 chart 切换
        next_win.tabs.setCurrentIndex(3)
        QTest.qWait(100)
        report_tab = next_win.tab_report
        for i in range(report_tab.chart_combo.count()):
            report_tab.chart_combo.setCurrentIndex(i)
            QTest.qWait(100)
            ct = report_tab.chart_combo.currentData()
            assert report_tab._canvas is not None
            _ok(f"  chart {i} '{ct}' canvas 渲染 OK")
        next_win.close()
        QTest.qWait(100)
    except Exception as e:
        _fail(f"管理员登录 + Tab/chart 切换失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # 5. 错误密码登录 (QMessageBox.warning monkey-patch 静默)
    # ====================================================
    _section("5. 错误密码登录 (应被 QMessageBox.warning 拦截)")
    try:
        win = LoginWindow()
        win.show()
        win.role_combo.setCurrentIndex(2)  # admin
        QTest.mouseClick(win.username_edit, Qt.LeftButton)
        QTest.keyClicks(win.username_edit, admin.username)
        QTest.mouseClick(win.password_edit, Qt.LeftButton)
        QTest.keyClicks(win.password_edit, "WRONG_PASSWORD")
        QTest.mouseClick(win.login_btn, Qt.LeftButton)
        QTest.qWait(200)
        # 失败时 next_win 不应被创建
        if hasattr(win, "next_win") and win.next_win is not None:
            _fail("错误密码居然登录成功?!")
            return 1
        _ok("错误密码拦截 OK (next_win 未创建)")
        win.close()
        QTest.qWait(100)
    except Exception as e:
        _fail(f"错误密码测试失败: {e}")
        import traceback; traceback.print_exc()
        return 1

    # ====================================================
    # cleanup
    # ====================================================
    _section("6. cleanup")
    try:
        with session_scope() as s:
            s.query(User).filter(User.username.like("smk_qt_%")).delete(synchronize_session=False)
        _ok("cleanup done")
    except Exception as e:
        _fail(f"cleanup 失败: {e}")

    print()
    print("[PASS] QTest 真实 UI 交互 5 步全过")
    print("       3 角色登录 + Tab 切换 + 4 chart 切换 + 错误密码拦截")
    return 0


if __name__ == "__main__":
    sys.exit(main())
