"""
tests/test_signin_code_dialog_integration.py — SigninCodeDialog 与 SigninWebServer 集成 (W14)

W14 UI 集成测试: 验证 SigninCodeDialog 在传入 web_server 参数后:
  1) 构造不抛异常 + 属性挂上 (web_server / _poll_timer / realtime_list)
  2) _render_code 在 web_server 不为 None 时用 web_server.url
  3) _render_code 在 web_server 为 None 时用裸 token (兜底)
  4) closeEvent 调 web_server.stop() (确保端口释放)
  5) closeEvent 停 polling timer
  6) append_signin_record 正确渲染到 QListWidget
  7) digit 类型不启 web_server (防御性: 即便传了也变 None)

设计取舍:
  - 不起真 SigninWebServer (避免端口分配 + threading 副作用), 用 MagicMock
  - 不起 Qt 事件循环 (offscreen 模式), 单测 widget 构造 + 方法调用契约
  - 两套 fixture:
      * patched_service_closed: generate_signin_code 返 None → dialog 构造后立刻 close
        (测 closeEvent 的副作用)
      * patched_service_alive: generate_signin_code 返合法 dict → dialog 保持 alive
        (测 _render_code / append_signin_record / polling 等业务方法)
"""
import os

# 强制 offscreen (CLAUDE.md 警告)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from PyQt5.QtWidgets import QApplication, QDialog


# =====================================================
# Fixtures
# =====================================================
@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    yield app


def _patch_service(monkeypatch, return_value):
    """通用 helper: 把 AttendanceService.generate_signin_code 改成返 return_value."""
    from src.ui.widgets import signin_code_dialog as scd_mod

    def fake_init(self):
        pass

    def fake_generate(self, task_id, code_type, ttl_seconds=60):
        return return_value

    monkeypatch.setattr(scd_mod.AttendanceService, "__init__", fake_init)
    scd_mod.AttendanceService.generate_signin_code = fake_generate
    monkeypatch.setattr(
        scd_mod.QMessageBox, "warning",
        staticmethod(lambda *a, **k: None),
    )
    return scd_mod


@pytest.fixture
def patched_service_closed(monkeypatch):
    """generate_signin_code 返 None → dialog 构造后立刻 self.close()。

    用于测 closeEvent 副作用 (停 timer / stop web_server / 兜底异常)。
    """
    return _patch_service(monkeypatch, return_value=None)


@pytest.fixture
def patched_service_alive(monkeypatch):
    """generate_signin_code 返合法 dict → dialog 保持 alive。

    用于测 _render_code / append_signin_record / start_polling_status 等。
    """
    return _patch_service(
        monkeypatch,
        return_value={
            "code": "fake-token-22chars-abc",
            "code_type": "qr",
            "expires_at": datetime.now() + timedelta(seconds=60),
        },
    )


def _make_fake_web_server(url: str = "http://192.168.1.100:5180/signin/42/fake-token"):
    """构造一个 MagicMock 充当 SigninWebServer。"""
    ws = MagicMock()
    ws.url = url
    ws.port = 5180
    ws.stop = MagicMock()
    return ws


# =====================================================
# Tests: 构造 + 参数接受
# =====================================================
def test_dialog_construct_accepts_web_server(qapp, patched_service_closed):
    """W14: SigninCodeDialog 构造签名扩展接受 web_server 参数, 不抛异常。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    dlg = SigninCodeDialog(
        parent=None, task_id=42, code_type="qr", teacher_window=None,
        web_server=ws,
    )
    try:
        assert isinstance(dlg, QDialog)
        assert dlg.task_id == 42
        # 构造期 closeEvent 已运行, web_server 应被清 (W14 行为)
        # 但 _init_ui 阶段 _build_realtime_list 应已挂上
        assert hasattr(dlg, "realtime_list"), "有 web_server 的 qr dialog 应有 realtime_list"
    finally:
        dlg.close()
        dlg.deleteLater()


def test_dialog_digit_type_ignores_web_server(qapp, patched_service_closed):
    """W14: 防御性 - digit 类型即便传了 web_server 也强制设 None (无意义)。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    dlg = SigninCodeDialog(
        parent=None, task_id=1, code_type="digit", web_server=ws,
    )
    try:
        # 防御性兜底: digit 类型不应启 web_server (避免数字码弹窗错起 H5 服务)
        assert dlg.web_server is None
        # 也不应有 realtime_list (那是 qr 专属)
        assert not hasattr(dlg, "realtime_list")
    finally:
        dlg.close()
        dlg.deleteLater()


# =====================================================
# Tests: closeEvent 副作用
# =====================================================
def test_dialog_close_event_stops_web_server(qapp, patched_service_closed):
    """W14: closeEvent 应调 web_server.stop() 释放端口。

    流程: __init__ → _generate_code → generate 返 None → self.close()
    → closeEvent → ws.stop() 至少被调一次
    """
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    dlg = SigninCodeDialog(
        parent=None, task_id=1, code_type="qr", web_server=ws,
    )
    try:
        # 构造期已 close, 验 stop 至少被调一次
        assert ws.stop.called, (
            "closeEvent 应至少调一次 web_server.stop() (释放端口)"
        )
    finally:
        dlg.deleteLater()


def test_dialog_close_event_swallows_web_server_exceptions(qapp, patched_service_closed):
    """W14: closeEvent 应吞掉 web_server.stop() 抛的异常, 不影响 widget 关闭。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    ws.stop.side_effect = RuntimeError("uvicorn 退出超时")

    dlg = SigninCodeDialog(
        parent=None, task_id=1, code_type="qr", web_server=ws,
    )
    # 构造期已 closeEvent 跑过 stop (异常被吞), 不应向外抛
    try:
        # 再次 close 也不应抛
        dlg.close()
    except RuntimeError as e:
        pytest.fail(f"closeEvent 不应向外抛 web_server.stop 异常: {e}")
    finally:
        dlg.deleteLater()


# =====================================================
# Tests: _render_code 路径选择
# =====================================================
def test_render_code_uses_web_server_url(qapp, patched_service_alive):
    """W14: _render_code 在 web_server 不为 None 时用 web_server.url。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    test_url = "http://10.0.0.5:5180/signin/99/abc-token-12345"
    ws = _make_fake_web_server(url=test_url)
    dlg = SigninCodeDialog(
        parent=None, task_id=99, code_type="qr", web_server=ws,
    )

    captured = {}

    def fake_make(data, *a, **kw):
        captured["data"] = data
        mock_img = MagicMock()
        mock_img.resize.return_value = mock_img
        mock_img.convert.return_value = mock_img
        return mock_img

    # patch sys.modules qrcode, 因为 _render_code 用局部 `import qrcode`
    import sys
    sys.modules["qrcode"] = MagicMock(make=fake_make)

    try:
        # 强制覆盖 _code_value 为「不应被使用」的值
        dlg._code_value = "should-not-be-used-as-qr-payload"
        dlg._render_code()
        assert captured.get("data") == test_url, (
            f"_render_code 应使用 web_server.url, 实际传 {captured.get('data')!r}"
        )
    finally:
        sys.modules.pop("qrcode", None)
        dlg.close()
        dlg.deleteLater()


def test_render_code_fallback_to_token_when_no_web_server(qapp, patched_service_alive):
    """W14: _render_code 在 web_server=None 时走兜底: 用裸 token。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    dlg = SigninCodeDialog(
        parent=None, task_id=1, code_type="qr", web_server=None,
    )
    assert dlg.web_server is None

    captured = {}

    def fake_make(data, *a, **kw):
        captured["data"] = data
        mock_img = MagicMock()
        mock_img.resize.return_value = mock_img
        mock_img.convert.return_value = mock_img
        return mock_img

    import sys
    sys.modules["qrcode"] = MagicMock(make=fake_make)

    try:
        dlg._code_value = "fallback-token-22chars"
        dlg._render_code()
        assert captured.get("data") == "fallback-token-22chars", (
            f"无 web_server 时 _render_code 应使用裸 token, 实际传 {captured.get('data')!r}"
        )
    finally:
        sys.modules.pop("qrcode", None)
        dlg.close()
        dlg.deleteLater()


# =====================================================
# Tests: 实时签到列表
# =====================================================
def test_append_signin_record_renders_to_listwidget(qapp, patched_service_alive):
    """W14: append_signin_record 把签到记录追加到 realtime_list 顶部。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    dlg = SigninCodeDialog(
        parent=None, task_id=42, code_type="qr", web_server=ws,
    )

    try:
        assert hasattr(dlg, "realtime_list"), (
            "有 web_server 的 qr dialog 应有 realtime_list"
        )

        # 模拟两条新签到 (最新在前面)
        dlg.append_signin_record({
            "student_name": "张三",
            "status": "present",
            "sign_in_time": "2026-06-16T18:09:33",
            "signin_method": "qr",
        })
        dlg.append_signin_record({
            "student_name": "李四",
            "status": "late",
            "sign_in_time": "2026-06-16T18:11:05",
            "signin_method": "qr",
        })

        assert dlg.realtime_list.count() == 2
        first_item = dlg.realtime_list.item(0)
        second_item = dlg.realtime_list.item(1)
        assert "李四" in first_item.text(), f"首条应为李四, 实际 {first_item.text()!r}"
        assert "张三" in second_item.text(), f"第二条应为张三, 实际 {second_item.text()!r}"
        # 时间截断到 HH:MM:SS
        assert "18:11:05" in first_item.text()
        assert "18:09:33" in second_item.text()
        # 中文标签
        assert "[扫码]" in first_item.text()
        assert "准时" in second_item.text()
    finally:
        dlg.close()
        dlg.deleteLater()


# =====================================================
# Tests: polling timer
# =====================================================
def test_dialog_close_stops_poll_timer(qapp, patched_service_alive):
    """W14: closeEvent 停 polling timer (避免 widget 销毁后 timer 仍触发 → 段错误)。

    验证方法:
      - 构造后 _poll_timer 是 QTimer 实例 (alive fixture 让 polling 自动启)
      - close 后 _poll_timer 被置 None (证明 timer 已被停)
      - 进一步: 通过 spy 记录 stop() 调用次数, 确认 stop 被显式调过
    """
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    dlg = SigninCodeDialog(
        parent=None, task_id=1, code_type="qr", web_server=ws,
    )

    try:
        # alive fixture → polling 自动启
        assert dlg._poll_timer is not None, (
            "alive dialog 应已启 polling (有 web_server + qr)"
        )
        original_timer = dlg._poll_timer

        # spy: wrap stop, 计数
        original_stop = original_timer.stop
        call_count = {"n": 0}
        def spy_stop():
            call_count["n"] += 1
            original_stop()
        original_timer.stop = spy_stop

        dlg.close()

        # closeEvent 应显式调 stop
        assert call_count["n"] >= 1, (
            f"closeEvent 应调 polling timer.stop(), 实际 {call_count['n']} 次"
        )
        # 引用应清空
        assert dlg._poll_timer is None, (
            "closeEvent 应把 _poll_timer 置 None"
        )
    finally:
        dlg.deleteLater()


def test_start_polling_is_idempotent(qapp, patched_service_alive):
    """W14: start_polling_status 多次调用只启一次 (避免 timer 累积)。"""
    from src.ui.widgets.signin_code_dialog import SigninCodeDialog
    ws = _make_fake_web_server()
    dlg = SigninCodeDialog(
        parent=None, task_id=1, code_type="qr", web_server=ws,
    )

    try:
        dlg.start_polling_status(interval_ms=10000)
        first_timer = dlg._poll_timer
        dlg.start_polling_status(interval_ms=20000)
        # 第二次 start 应不替换 timer
        assert dlg._poll_timer is first_timer, (
            "start_polling_status 应幂等 (重复调用不创建新 timer)"
        )
    finally:
        dlg.close()
        dlg.deleteLater()


# =====================================================
# Tests: teacher_window 集成 (源码 smoke)
# =====================================================
def test_teacher_window_uses_signin_web_for_qr(qapp):
    """W14: teacher_window._on_open_signin_dialog 源码里引用了 SigninWebServer。

    用 inspect.getsource 直接读源码, 不实例化 TeacherWindow (避免 PyQt 段错误)。
    """
    from src.ui import teacher_window as tw_mod
    # 方法在类上, 不是 module-level
    src = tw_mod.TeacherWindow.__dict__["_on_open_signin_dialog"].__code__
    import inspect
    src_text = inspect.getsource(src)
    assert "SigninWebServer" in src_text, (
        "_on_open_signin_dialog 应引用 SigninWebServer"
    )
    assert "generate_signin_code" in src_text, (
        "_on_open_signin_dialog 应提前调 generate_signin_code 拿 token"
    )
    assert "web_server.start()" in src_text, (
        "_on_open_signin_dialog 应调 web_server.start()"
    )
    # 仅 qr 启 web_server (digit 保持原行为)
    assert 'code_type == "qr"' in src_text or "code_type == 'qr'" in src_text, (
        "_on_open_signin_dialog 应只在 code_type='qr' 时启 web_server"
    )
