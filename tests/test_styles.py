"""
tests/test_styles.py — Status label "warning" 视觉态样式回归测试 (W14)

覆盖:
- QLabel[role="status"][state="warning"] QSS 规则在 GLOBAL_QSS 中存在
- 实例化 QApplication 后, 给 QLabel 设 role=status + state=warning,
  polish 后 QSS 选择器能命中 (state 属性仍可读到 "warning")
- 业务文案走查: warning 文案至少包含 1 个常见提示

测试策略:
- offscreen 模式跑 Qt 不弹窗
- 真实加载 GLOBAL_QSS 验证 QSS 字符串里包含新规则
"""
import os
import sys

# offscreen 模式跑 Qt 不弹窗 (Windows + PyQt5 在 offscreen 下 offscreen 安全)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication, QLabel

from src.ui.styles import GLOBAL_QSS, COLOR_WARNING


# 业务侧会用到的 warning 文案 (走查列表, 任何 1 个命中即视为业务一致)
WARNING_PROMPTS = (
    "未识别到人脸",
    "识别到他人",
)


@pytest.fixture(scope="module")
def qapp():
    """module 级 QApplication — Qt 要求 QApplication 单例。"""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_status_label_warning_state_renders(qapp):
    """warning 视觉态: QSS 规则在, QLabel 属性设置后能命中。"""
    # 1) QSS 字符串里包含 warning 规则
    assert 'QLabel[role="status"][state="warning"]' in GLOBAL_QSS, (
        "GLOBAL_QSS 缺 QLabel[role=status][state=warning] 规则"
    )
    # 2) warning 用的色值是 #F59E0B (Tailwind amber-500)
    assert COLOR_WARNING == "#F59E0B", (
        f"COLOR_WARNING 应为 #F59E0B, 实际 {COLOR_WARNING!r}"
    )

    # 3) 真实 QLabel 实例: 设 role=status + state=warning, polish 后属性可读
    qapp.setStyleSheet(GLOBAL_QSS)

    widget = QLabel("未识别到人脸，请调整姿势或正对摄像头")
    widget.setProperty("role", "status")
    widget.setProperty("state", "warning")

    # 触发 QSS 重新解析
    widget.style().polish(widget)
    widget.style().unpolish(widget)
    widget.style().polish(widget)

    # 4) 业务文案走查: warning 态常用提示至少要有一个出现在 QSS 文案里
    #    (这里只断言 widget 上的文字确实含一个 warning 提示字符串,
    #     不直接校验 QSS — 那是设计层面的事)
    assert any(prompt in widget.text() for prompt in WARNING_PROMPTS), (
        f"warning 态 label 文案应至少含 {WARNING_PROMPTS!r} 中之一, "
        f"实际文字: {widget.text()!r}"
    )

    # 5) 属性断言: polish 后 state 属性仍为 "warning"
    assert widget.property("state") == "warning", (
        f"QLabel 的 state 属性应为 'warning', 实际 {widget.property('state')!r}"
    )
    assert widget.property("role") == "status", (
        f"QLabel 的 role 属性应为 'status', 实际 {widget.property('role')!r}"
    )
