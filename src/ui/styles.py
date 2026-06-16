"""
ui/styles.py — 全局 QSS / 色板 / Design Tokens

集中维护整套配色 / 字体 / 圆角 / 间距 / 阴影，避免在每个窗口里重复写。
调用入口:
    from src.ui.styles import apply_global_style
    apply_global_style(app)

设计目标 (W14 课程交付物):
- 天蓝现代商务风 (Tailwind blue 系)
- Design Tokens 化: 颜色 / 圆角 / 阴影 / 字体 / 间距统一从模块顶部常量读取
- 表单/按钮/表格/标签页 全面现代化
- 保持现有 dynamic-property 规则: role=primary / role=danger / role=status[state=*]
"""
from PyQt5.QtWidgets import QApplication

from src.models.user import User

# =====================================================================
# 1. Design Tokens —— 颜色
# =====================================================================
# 天蓝系 (Tailwind blue 调色盘)
COLOR_PRIMARY = "#1E40AF"        # blue-800 - 深蓝，用于 header 背景
COLOR_ACCENT = "#3B82F6"         # blue-500 - 中亮蓝，hover/active
COLOR_BUTTON = "#2563EB"         # blue-600 - 主按钮蓝
COLOR_BUTTON_HOVER = "#1D4ED8"   # blue-700
COLOR_BUTTON_PRESSED = "#1E40AF"  # blue-800
COLOR_BORDER_FOCUS = "#2563EB"   # blue-600

# 中性色 (Tailwind slate/gray 系)
COLOR_BG = "#F4F5F7"             # 窗口背景 (更现代的浅灰)
COLOR_BG_CARD = "#FFFFFF"        # 卡片/输入框背景
COLOR_BORDER = "#E5E7EB"         # gray-200 - 更柔的灰边
COLOR_TEXT = "#111827"           # slate-900 - 主文字
COLOR_TEXT_MUTED = "#6B7280"     # gray-500 - 次要文字

# 语义色 (Tailwind)
COLOR_DANGER = "#EF4444"         # red-500
COLOR_WARNING = "#F59E0B"        # amber-500 - 保留 (业务 warning 状态色，回归测试锁定)
COLOR_SUCCESS = "#10B981"        # emerald-500

# =====================================================================
# 2. Design Tokens —— 几何
# =====================================================================
RADIUS_SM = "6px"    # 按钮/输入框
RADIUS_MD = "10px"   # 卡片/GroupBox
RADIUS_LG = "14px"   # 大卡片/Auth header

# 阴影
SHADOW_CARD = "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)"   # 卡片阴影
SHADOW_MODAL = "0 8px 24px rgba(0,0,0,0.12)"                            # 弹窗阴影

# =====================================================================
# 3. Design Tokens —— 字体
# =====================================================================
FONT_FAMILY = "Microsoft YaHei UI"  # Win 自带；缺字回落到系统默认
# W14+ 演示模式: 答辩/录屏场景字号 +2-6px, 1080P 投影 / 笔记本 14" 都不挤
FONT_SIZE_BASE = "16px"      # 14 → 16, 全局 base 文字 (表单/列表/正文)
FONT_SIZE_TITLE = "18px"     # 16 → 18, Tab/卡片标题
FONT_SIZE_HEADING = "26px"   # 20 → 26, 大标题 (Welcome、弹窗头)
FONT_WEIGHT_BOLD = "600"

# =====================================================================
# 4. Design Tokens —— 间距
# =====================================================================
SPACING_XS = "4px"
SPACING_SM = "8px"
SPACING_MD = "12px"
SPACING_LG = "16px"
SPACING_XL = "24px"


# =====================================================================
# 5. 全局 QSS (作用于 QApplication)
# =====================================================================
# 作用范围: 所有未单独 setStyleSheet 的控件
# 重点: 字体/背景/输入框/按钮/GroupBox/状态标签/表格/标签页
GLOBAL_QSS = f"""
* {{
    font-family: "{FONT_FAMILY}", "Segoe UI", "Microsoft YaHei", sans-serif;
    font-size: {FONT_SIZE_BASE};
    color: {COLOR_TEXT};
}}

QWidget {{
    background-color: {COLOR_BG};
}}

/* —— GroupBox 卡片化 —— */
QGroupBox {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_MD};
    margin-top: 14px;
    padding: 20px 16px 14px 16px;
    font-weight: {FONT_WEIGHT_BOLD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: {COLOR_PRIMARY};
}}

/* —— 输入框 —— */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_SM};
    padding: 8px 10px;
    selection-background-color: {COLOR_BUTTON};
    selection-color: white;
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QDateEdit:focus, QTimeEdit:focus, QDateTimeEdit:focus {{
    border: 1px solid {COLOR_BORDER_FOCUS};
    background-color: #FAFBFF;
}}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
    border: 1px solid #CBD5E1;
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
    border-radius: {RADIUS_SM};
    padding: 8px 18px;
    min-width: 88px;
    font-weight: {FONT_WEIGHT_BOLD};
}}
QPushButton:hover {{
    border: 1px solid {COLOR_BUTTON};
    color: {COLOR_BUTTON};
    background-color: #F8FAFF;
}}
QPushButton:pressed {{
    background-color: #EEF2FF;
    color: {COLOR_BUTTON_PRESSED};
    border: 1px solid {COLOR_BUTTON_PRESSED};
}}
QPushButton:disabled {{
    color: {COLOR_TEXT_MUTED};
    background-color: #F1F5F9;
    border: 1px solid {COLOR_BORDER};
}}

/* —— 主按钮 (用于登录/提交) —— */
QPushButton[role="primary"] {{
    background-color: {COLOR_BUTTON};
    color: white;
    border: 1px solid {COLOR_BUTTON};
    font-weight: {FONT_WEIGHT_BOLD};
}}
QPushButton[role="primary"]:hover {{
    background-color: {COLOR_BUTTON_HOVER};
    border: 1px solid {COLOR_BUTTON_HOVER};
    color: white;
}}
QPushButton[role="primary"]:pressed {{
    background-color: {COLOR_BUTTON_PRESSED};
    border: 1px solid {COLOR_BUTTON_PRESSED};
    color: white;
}}
QPushButton[role="primary"]:disabled {{
    background-color: #93C5FD;
    border: 1px solid #93C5FD;
    color: white;
}}

/* —— 危险按钮 (退出/删除) —— */
QPushButton[role="danger"] {{
    color: {COLOR_DANGER};
    border: 1px solid {COLOR_DANGER};
    background-color: white;
    font-weight: {FONT_WEIGHT_BOLD};
}}
QPushButton[role="danger"]:hover {{
    background-color: {COLOR_DANGER};
    color: white;
    border: 1px solid {COLOR_DANGER};
}}
QPushButton[role="danger"]:pressed {{
    background-color: #DC2626;
    border: 1px solid #DC2626;
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
QLabel[role="status"][state="warning"] {{
    color: {COLOR_WARNING};
}}

/* —— 表单 label —— */
QLabel {{
    padding: 0;
}}

/* —— 表格: 表头深底白字 / 斑马纹 / 行高加大 —— */
QTableWidget, QTableView {{
    background-color: {COLOR_BG_CARD};
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_SM};
    gridline-color: #EEF2F7;
    selection-background-color: #DBEAFE;
    selection-color: {COLOR_TEXT};
    alternate-background-color: #F8FAFC;
}}
QTableWidget::item, QTableView::item {{
    padding: 8px 6px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: #DBEAFE;
    color: {COLOR_TEXT};
}}
QHeaderView::section {{
    background-color: {COLOR_PRIMARY};
    color: white;
    padding: 10px 8px;
    border: none;
    font-weight: {FONT_WEIGHT_BOLD};
    font-size: {FONT_SIZE_BASE};
}}
QHeaderView::section:first {{
    border-top-left-radius: {RADIUS_SM};
}}
QHeaderView::section:last {{
    border-top-right-radius: {RADIUS_SM};
}}

/* —— 标签页: 现代化 (无方框/active 蓝色下划线) —— */
QTabWidget::pane {{
    border: 1px solid {COLOR_BORDER};
    border-radius: {RADIUS_MD};
    background-color: {COLOR_BG_CARD};
    top: -1px;
}}
QTabBar {{
    background: transparent;
}}
QTabBar::tab {{
    background: transparent;
    color: {COLOR_TEXT_MUTED};
    padding: 10px 18px;
    border: none;
    border-bottom: 2px solid transparent;
    margin-right: 4px;
    font-weight: {FONT_WEIGHT_BOLD};
}}
QTabBar::tab:hover {{
    color: {COLOR_BUTTON};
}}
QTabBar::tab:selected {{
    color: {COLOR_BUTTON};
    border-bottom: 2px solid {COLOR_BUTTON};
    background-color: transparent;
}}

/* —— 滚动条 —— */
QScrollBar:vertical {{
    background: {COLOR_BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #CBD5E1;
    border-radius: 5px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{
    background: {COLOR_ACCENT};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {COLOR_BG};
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #CBD5E1;
    border-radius: 5px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {COLOR_ACCENT};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
"""


# =====================================================================
# 6. Auth 窗专用 QSS (叠加在 GLOBAL 之上)
# =====================================================================
# 作用: 登录/注册窗的标题栏 + 品牌区
AUTH_HEADER_QSS = f"""
QWidget#AuthHeader {{
    background-color: {COLOR_PRIMARY};
    border-top-left-radius: {RADIUS_LG};
    border-top-right-radius: {RADIUS_LG};
}}
QLabel#AuthHeaderTitle {{
    color: white;
    font-size: {FONT_SIZE_HEADING};
    font-weight: {FONT_WEIGHT_BOLD};
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
    border-radius: {RADIUS_SM};
    padding: 3px 8px;
    font-size: 10px;
    font-weight: {FONT_WEIGHT_BOLD};
    letter-spacing: 1px;
}}
"""


# =====================================================================
# 7. 入口函数 (保持现有签名不变)
# =====================================================================
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
    return {
        "student": " 同学",
        "teacher": " 老师",
        "lab_admin": " 管理员",
    }.get(user.role, "")
