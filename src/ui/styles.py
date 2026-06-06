"""
ui/styles.py — 全局 QSS 与色板

集中维护整套配色 / 字体 / 圆角 / 间距，避免在每个窗口里重复写。
调用入口：
    from src.ui.styles import apply_global_style
    apply_global_style(app)
"""
from PyQt5.QtWidgets import QApplication

from src.models.user import User

# ---------- 色板 ----------
COLOR_PRIMARY = "#1E3A5F"     # 深藏青（标题栏/强调）
COLOR_ACCENT = "#2C5282"      # 中藏青
COLOR_BUTTON = "#2563EB"      # 主按钮
COLOR_BUTTON_HOVER = "#1D4ED8"
COLOR_BUTTON_PRESSED = "#1E40AF"
COLOR_TEXT = "#1F2937"
COLOR_TEXT_MUTED = "#6B7280"
COLOR_BG = "#F8FAFC"          # 窗口背景
COLOR_BG_CARD = "#FFFFFF"     # 卡片/输入框
COLOR_BORDER = "#CBD5E1"
COLOR_BORDER_FOCUS = "#2563EB"
COLOR_DANGER = "#DC2626"
COLOR_WARNING = "#D97706"     # 橙（介于 success 和 danger 之间）
COLOR_SUCCESS = "#16A34A"

# ---------- 字体 ----------
FONT_FAMILY = "Microsoft YaHei UI"  # Win 自带；缺字回落到系统默认

# ---------- 全局 QSS（作用于 QApplication） ----------
# 作用范围：所有未单独 setStyleSheet 的控件。
# 重点：表单容器、按钮、输入框、GroupBox、状态标签。
GLOBAL_QSS = f"""
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI", "Microsoft YaHei", sans-serif;
    color: {COLOR_TEXT};
}}

QWidget {{
    background-color: {COLOR_BG};
}}

/* —— GroupBox 卡片化 —— */
QGroupBox {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 18px 14px 12px 14px;
    font-weight: bold;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {COLOR_PRIMARY};
}}

/* —— 输入框 —— */
QLineEdit, QComboBox {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 10px;
    selection-background-color: {COLOR_BUTTON};
    selection-color: white;
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus {{
    border: 1px solid {COLOR_BORDER_FOCUS};
}}
QLineEdit:disabled, QComboBox:disabled {{
    background-color: #F1F5F9;
    color: {COLOR_TEXT_MUTED};
}}

/* —— 按钮 —— */
QPushButton {{
    background-color: {COLOR_BG_CARD};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 8px 18px;
    min-width: 88px;
}}
QPushButton:hover {{
    border: 1px solid {COLOR_BUTTON};
    color: {COLOR_BUTTON};
}}
QPushButton:pressed {{
    background-color: #EEF2FF;
}}
QPushButton:disabled {{
    color: {COLOR_TEXT_MUTED};
    background-color: #F1F5F9;
}}

/* —— 主按钮（用于登录/提交）—— */
QPushButton[role="primary"] {{
    background-color: {COLOR_BUTTON};
    color: white;
    border: 1px solid {COLOR_BUTTON};
    font-weight: bold;
}}
QPushButton[role="primary"]:hover {{
    background-color: {COLOR_BUTTON_HOVER};
    border: 1px solid {COLOR_BUTTON_HOVER};
    color: white;
}}
QPushButton[role="primary"]:pressed {{
    background-color: {COLOR_BUTTON_PRESSED};
    border: 1px solid {COLOR_BUTTON_PRESSED};
}}
QPushButton[role="primary"]:disabled {{
    background-color: #93C5FD;
    border: 1px solid #93C5FD;
    color: white;
}}

/* —— 危险按钮（退出/删除）—— */
QPushButton[role="danger"] {{
    color: {COLOR_DANGER};
    border: 1px solid {COLOR_DANGER};
}}
QPushButton[role="danger"]:hover {{
    background-color: {COLOR_DANGER};
    color: white;
}}

/* —— 状态/提示文字 —— */
QLabel[role="status"] {{
    color: {COLOR_TEXT_MUTED};
    padding: 4px 2px;
}}
QLabel[role="status"][state="error"] {{
    color: {COLOR_DANGER};
}}
QLabel[role="status"][state="success"] {{
    color: {COLOR_SUCCESS};
}}

/* —— 表单 label 右对齐 —— */
QLabel {{
    padding: 0;
}}
"""

# ---------- Auth 窗专用 QSS（叠加在 GLOBAL 之上） ----------
# 作用：登录/注册窗的标题栏 + 品牌区
AUTH_HEADER_QSS = f"""
QWidget#AuthHeader {{
    background-color: {COLOR_PRIMARY};
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
}}
QLabel#AuthHeaderTitle {{
    color: white;
    font-size: 18px;
    font-weight: bold;
    background: transparent;
}}
QLabel#AuthHeaderSubtitle {{
    color: #CBD5E1;
    font-size: 11px;
    background: transparent;
}}
QLabel#AuthHeaderBadge {{
    color: {COLOR_PRIMARY};
    background-color: white;
    border-radius: 4px;
    padding: 3px 8px;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}}
"""


def apply_global_style(app: QApplication) -> None:
    """在 QApplication 创建后调用一次，注入全局 QSS。"""
    app.setStyleSheet(GLOBAL_QSS)


def apply_auth_style(window) -> None:
    """登录/注册窗在构造时调用，叠加 Auth 专用样式。"""
    window.setStyleSheet(AUTH_HEADER_QSS)


def welcome_suffix(user: User) -> str:
    """按角色加称呼后缀；若 real_name 已自带（同学/老师/管理员/主任/教授）则不叠加。"""
    name = user.real_name or ""
    if any(name.endswith(s) for s in ("同学", "老师", "管理员", "主任", "教授")):
        return ""
    return {"student": " 同学", "teacher": " 老师"}.get(user.role, "")
