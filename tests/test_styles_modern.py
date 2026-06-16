"""
tests/test_styles_modern.py — 现代天蓝主题 + Design Tokens 回归测试 (W14)

覆盖:
a) 所有新 tokens 已定义且类型正确 (颜色 tokens / 几何 / 字体 / 间距)
b) 天蓝主色 #2563EB 在 GLOBAL_QSS 出现 >= 3 处 (主按钮/边框 focus/selection 至少各一处)
c) 现有 warning state 视觉态规则未被破坏 (回归保护 — 业务 warning 提示走 warning 配色)
d) GroupBox / QPushButton / QLineEdit 规则都存在
e) QTableWidget 表头深底白字规则存在 (现代化表格)
f) AUTH_HEADER_QSS 引用 COLOR_PRIMARY
g) apply_global_style 可调用且不抛异常 (用 module 级 QApplication mock)

测试策略:
- offscreen 模式跑 Qt 不弹窗
- 大部分断言基于 GLOBAL_QSS 字符串 + 顶层 token 常量
- apply_global_style 用真实 QApplication 验证可调用
"""
import os
import sys
from unittest.mock import MagicMock

# offscreen 模式跑 Qt 不弹窗
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt5")

from PyQt5.QtWidgets import QApplication

from src.ui import styles
from src.ui.styles import (
    GLOBAL_QSS,
    AUTH_HEADER_QSS,
    # 颜色
    COLOR_PRIMARY,
    COLOR_ACCENT,
    COLOR_BUTTON,
    COLOR_BUTTON_HOVER,
    COLOR_BUTTON_PRESSED,
    COLOR_BG,
    COLOR_BG_CARD,
    COLOR_BORDER,
    COLOR_BORDER_FOCUS,
    COLOR_DANGER,
    COLOR_WARNING,
    COLOR_SUCCESS,
    COLOR_TEXT,
    COLOR_TEXT_MUTED,
    # 几何
    RADIUS_SM,
    RADIUS_MD,
    RADIUS_LG,
    SHADOW_CARD,
    SHADOW_MODAL,
    # 字体
    FONT_FAMILY,
    FONT_SIZE_BASE,
    FONT_SIZE_TITLE,
    FONT_SIZE_HEADING,
    FONT_WEIGHT_BOLD,
    # 间距
    SPACING_XS,
    SPACING_SM,
    SPACING_MD,
    SPACING_LG,
    SPACING_XL,
    # 入口函数
    apply_global_style,
    apply_auth_style,
    welcome_suffix,
)


# ============================================================
# a) 所有新 tokens 已定义且类型正确
# ============================================================
class TestDesignTokens:
    """所有 design tokens 都已定义、类型正确、值符合天蓝现代商务风。"""

    def test_color_tokens_are_hex_strings(self):
        """颜色 token 必须是 #RRGGBB 形式的字符串 (天蓝/Tailwind 调色盘)。"""
        expected_colors = {
            COLOR_PRIMARY: "#1E40AF",
            COLOR_ACCENT: "#3B82F6",
            COLOR_BUTTON: "#2563EB",
            COLOR_BUTTON_HOVER: "#1D4ED8",
            COLOR_BUTTON_PRESSED: "#1E40AF",
            COLOR_BG: "#F4F5F7",
            COLOR_BG_CARD: "#FFFFFF",
            COLOR_BORDER: "#E5E7EB",
            COLOR_BORDER_FOCUS: "#2563EB",
            COLOR_DANGER: "#EF4444",
            COLOR_WARNING: "#F59E0B",
            COLOR_SUCCESS: "#10B981",
            COLOR_TEXT: "#111827",
            COLOR_TEXT_MUTED: "#6B7280",
        }
        for actual, expected in expected_colors.items():
            assert isinstance(actual, str), f"颜色 token 必须是字符串, 实际 {type(actual)}"
            assert actual == expected, (
                f"颜色 token 应为 {expected}, 实际 {actual}"
            )
            # 简单格式校验
            assert actual.startswith("#") and len(actual) == 7, (
                f"颜色 token 应为 #RRGGBB 7 位, 实际 {actual!r}"
            )

    def test_radius_tokens_are_px_strings(self):
        """圆角 token 必须是带 px 的字符串。"""
        for r in (RADIUS_SM, RADIUS_MD, RADIUS_LG):
            assert isinstance(r, str)
            assert r.endswith("px"), f"圆角 token 应以 px 结尾, 实际 {r!r}"
        # 顺序: SM <= MD <= LG
        assert int(RADIUS_SM[:-2]) < int(RADIUS_MD[:-2]) < int(RADIUS_LG[:-2])

    def test_shadow_tokens_are_non_empty_strings(self):
        """阴影 token 必须是非空字符串 (rgba 阴影定义)。"""
        assert isinstance(SHADOW_CARD, str) and "rgba" in SHADOW_CARD
        assert isinstance(SHADOW_MODAL, str) and "rgba" in SHADOW_MODAL

    def test_font_tokens_defined(self):
        """字体 token: 字体名 + 3 个字号 + 字重。"""
        assert isinstance(FONT_FAMILY, str) and len(FONT_FAMILY) > 0
        for fs in (FONT_SIZE_BASE, FONT_SIZE_TITLE, FONT_SIZE_HEADING):
            assert isinstance(fs, str) and fs.endswith("px")
        assert isinstance(FONT_WEIGHT_BOLD, str) and FONT_WEIGHT_BOLD == "600"

    def test_spacing_tokens_are_ordered_px_strings(self):
        """间距 token: 5 档，XS < SM < MD < LG < XL (像素值严格递增)。"""
        spacings = [SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG, SPACING_XL]
        for s in spacings:
            assert isinstance(s, str) and s.endswith("px"), (
                f"间距 token 应为 px 字符串, 实际 {s!r}"
            )
        values = [int(s[:-2]) for s in spacings]
        assert values == sorted(values), (
            f"间距 token 应递增, 实际 {values}"
        )
        assert values == [4, 8, 12, 16, 24], (
            f"间距 token 期望 [4, 8, 12, 16, 24], 实际 {values}"
        )


# ============================================================
# b) 天蓝主色 #2563EB 在 GLOBAL_QSS 出现 >= 3 处
# ============================================================
def test_sky_blue_primary_color_appears_multiple_times():
    """天蓝主色 #2563EB (COLOR_BUTTON / COLOR_BORDER_FOCUS) 在 GLOBAL_QSS 出现 >= 3 次。

    至少出现位置:
    - QPushButton[role="primary"] 背景/边框
    - QLineEdit/QComboBox focus 边框
    - selection-background-color
    - QTabBar::tab:selected 蓝色下划线 (用 COLOR_BUTTON)
    """
    occurrences = GLOBAL_QSS.count("#2563EB")
    assert occurrences >= 3, (
        f"天蓝主色 #2563EB 至少应出现 3 次, 实际 {occurrences} 次"
    )


def test_sky_blue_color_matches_button_token():
    """#2563EB 在 GLOBAL_QSS 中的出现应与 COLOR_BUTTON 一致。"""
    assert COLOR_BUTTON == "#2563EB"
    # QPushButton[role="primary"] 规则应包含 COLOR_BUTTON
    assert "QPushButton[role=\"primary\"]" in GLOBAL_QSS
    # role=primary 段附近 (前后 200 字符) 应包含 #2563EB
    primary_idx = GLOBAL_QSS.find("QPushButton[role=\"primary\"]")
    nearby = GLOBAL_QSS[primary_idx:primary_idx + 400]
    assert "#2563EB" in nearby, (
        f"QPushButton[role=primary] 段应引用 #2563EB, 实际段: {nearby[:200]!r}"
    )


# ============================================================
# c) warning state 视觉态规则未被破坏 (回归保护)
# ============================================================
def test_warning_state_visual_rule_preserved():
    """QLabel[role=status][state=warning] 规则必须保留，引用 COLOR_WARNING (#F59E0B)。"""
    assert 'QLabel[role="status"][state="warning"]' in GLOBAL_QSS, (
        "GLOBAL_QSS 缺 QLabel[role=status][state=warning] 规则 (回归保护)"
    )
    assert COLOR_WARNING == "#F59E0B", (
        f"COLOR_WARNING 应为 #F59E0B, 实际 {COLOR_WARNING!r}"
    )
    # warning 段附近应包含 #F59E0B
    warn_idx = GLOBAL_QSS.find('QLabel[role="status"][state="warning"]')
    nearby = GLOBAL_QSS[warn_idx:warn_idx + 200]
    assert "#F59E0B" in nearby, (
        f"warning 段应引用 #F59E0B, 实际段: {nearby[:200]!r}"
    )


# ============================================================
# d) GroupBox / QPushButton / QLineEdit 规则都存在
# ============================================================
def test_groupbox_pushbutton_lineedit_rules_exist():
    """核心控件 QSS 规则必须都在。"""
    assert "QGroupBox" in GLOBAL_QSS, "缺 QGroupBox 规则"
    assert "QPushButton" in GLOBAL_QSS, "缺 QPushButton 规则"
    assert "QLineEdit" in GLOBAL_QSS, "缺 QLineEdit 规则"
    # 必须支持 role=primary / role=danger 两个 dynamic property
    assert 'QPushButton[role="primary"]' in GLOBAL_QSS
    assert 'QPushButton[role="danger"]' in GLOBAL_QSS
    # 圆角 token 必须出现在这些规则中
    assert RADIUS_SM in GLOBAL_QSS, (
        f"RADIUS_SM ({RADIUS_SM}) 应在 GLOBAL_QSS 中"
    )


# ============================================================
# e) QTableWidget 表头深底白字规则存在
# ============================================================
def test_table_widget_modern_header_rule_exists():
    """QTableWidget / QHeaderView 现代化规则: 表头深底白字 + 圆角 + 斑马纹。"""
    assert "QTableWidget" in GLOBAL_QSS, "缺 QTableWidget 规则"
    assert "QHeaderView::section" in GLOBAL_QSS, (
        "缺 QHeaderView::section 表头规则"
    )
    # 表头应使用 COLOR_PRIMARY 背景 + 白色文字
    header_idx = GLOBAL_QSS.find("QHeaderView::section")
    header_block = GLOBAL_QSS[header_idx:header_idx + 400]
    assert COLOR_PRIMARY in header_block, (
        f"QHeaderView::section 应使用 COLOR_PRIMARY ({COLOR_PRIMARY}) 背景, "
        f"实际: {header_block[:200]!r}"
    )
    assert "color: white" in header_block, (
        f"QHeaderView::section 文字应为 white, 实际: {header_block[:200]!r}"
    )
    # 斑马纹 (alternate-background-color)
    assert "alternate-background-color" in GLOBAL_QSS, (
        "缺 alternate-background-color 斑马纹规则"
    )


# ============================================================
# f) AUTH_HEADER_QSS 引用 COLOR_PRIMARY
# ============================================================
def test_auth_header_qss_uses_color_primary():
    """AUTH_HEADER_QSS 的品牌区背景应使用 COLOR_PRIMARY。"""
    assert "QWidget#AuthHeader" in AUTH_HEADER_QSS, "缺 AuthHeader 规则"
    auth_block_idx = AUTH_HEADER_QSS.find("QWidget#AuthHeader")
    auth_block = AUTH_HEADER_QSS[auth_block_idx:auth_block_idx + 300]
    assert COLOR_PRIMARY in auth_block, (
        f"AuthHeader 应使用 COLOR_PRIMARY ({COLOR_PRIMARY}) 背景, "
        f"实际: {auth_block[:200]!r}"
    )
    # 圆角用 RADIUS_LG
    assert RADIUS_LG in AUTH_HEADER_QSS, (
        f"AUTH_HEADER_QSS 应引用 RADIUS_LG ({RADIUS_LG})"
    )


# ============================================================
# g) apply_global_style 可调用且不抛异常
# ============================================================
@pytest.fixture(scope="module")
def qapp():
    """module 级 QApplication — Qt 要求 QApplication 单例。"""
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_apply_global_style_callable_with_qapp(qapp):
    """apply_global_style 接受 QApplication 并 setStyleSheet 不抛异常。"""
    # 先备份原始 stylesheet 以便还原
    original = qapp.styleSheet()
    try:
        apply_global_style(qapp)
        # 注入后 QApplication 的 stylesheet 应非空
        current = qapp.styleSheet()
        assert current, "apply_global_style 后 QApplication stylesheet 应非空"
        assert "QGroupBox" in current, (
            "注入的 stylesheet 应含 QGroupBox 规则 (sanity check)"
        )
        assert "QPushButton[role=\"primary\"]" in current
    finally:
        # 还原原始 stylesheet，避免污染后续测试
        qapp.setStyleSheet(original)


def test_apply_global_style_with_mock_app_does_not_raise():
    """apply_global_style 接受任意有 setStyleSheet 方法的对象 (用 MagicMock) 不抛异常。

    这是契约测试: styles.py 只依赖 app.setStyleSheet 这一个接口。
    """
    mock_app = MagicMock()
    # 不应抛异常
    apply_global_style(mock_app)
    # 必须被调用一次，且参数是 GLOBAL_QSS
    assert mock_app.setStyleSheet.called
    call_args = mock_app.setStyleSheet.call_args
    assert call_args[0][0] == GLOBAL_QSS, (
        f"apply_global_style 应传入 GLOBAL_QSS, 实际 {call_args[0][0][:80]!r}"
    )


def test_entry_functions_signatures_preserved():
    """入口函数签名保持不变 (回归保护)。"""
    import inspect
    # apply_global_style(app: QApplication) -> None
    sig = inspect.signature(apply_global_style)
    assert list(sig.parameters.keys()) == ["app"]
    # apply_auth_style(window) -> None
    sig = inspect.signature(apply_auth_style)
    assert list(sig.parameters.keys()) == ["window"]
    # welcome_suffix(user: User) -> str
    sig = inspect.signature(welcome_suffix)
    assert list(sig.parameters.keys()) == ["user"]
