"""
ui/admin_window.py — 实验室管理员端主窗口

W4 Phase 5 接入进度:
- ✅ Tab 1 实验室管理: CRUD（Phase 5a 完成）
- ✅ Tab 2 安全培训录入: CRUD（Phase 5b完成）
- ✅ Tab 3 准入日志: 只读 + 筛选（Phase 5c完成）
- ✅ Tab 4 使用率报表: matplotlib 嵌入 + 4 类图表切换（Phase 5d完成）
- ✅ Tab 5 用户人脸管理: 删 face_encoding + jpg (W12 新增)

self.tabs 标准命名（跟 StudentWindow/TeacherWindow 一致）
"""
import logging

from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.models.user import User
from src.ui.styles import welcome_suffix

log = logging.getLogger(__name__)


class AdminWindow(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"实验室管理员端 — {self.user.real_name}")
        # W14+ 演示模式: 窗口 +140x120 容纳 matplotlib 大字号坐标 + 表格更舒展
        self.resize(1280, 860)

        # W14: 顶部信息条 spacing 加大, 与 teacher/student 风格一致
        top = QHBoxLayout()
        top.setSpacing(16)
        welcome = QLabel(f"欢迎，{self.user.real_name}{welcome_suffix(self.user)}")
        # W14+ 演示模式: Welcome 字号 12→15
        f = QFont(); f.setPointSize(15); f.setBold(True)
        welcome.setFont(f)
        top.addWidget(welcome)
        top.addStretch()
        top.addWidget(QLabel(f"用户名: {self.user.username} | 角色: 实验室管理员"))
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        self.tabs = QTabWidget()
        # W14 现代化: Tab 控件 document 模式, 配合 GLOBAL_QSS 的 QTabBar::tab 现代化样式
        self.tabs.setDocumentMode(True)
        # Tab 1 实验室管理（Phase 5a 完成）
        from src.ui.widgets.lab_admin_tab import LabAdminTab
        self.tab_lab = LabAdminTab()
        self.tabs.addTab(self.tab_lab, "🏛 实验室管理")

        # Tab 2 安全培训录入（Phase 5b 完成）
        from src.ui.widgets.training_admin_tab import TrainingAdminTab
        self.tab_training = TrainingAdminTab()
        self.tabs.addTab(self.tab_training, "📋 安全培训")

        # Tab 3 准入日志（Phase 5c 完成）
        from src.ui.widgets.access_log_tab import AccessLogTab
        self.tab_log = AccessLogTab()
        self.tabs.addTab(self.tab_log, "🚪 准入日志")

        # Tab 4 使用率报表（Phase 5d 完成）
        from src.ui.widgets.report_admin_tab import ReportAdminTab
        self.tab_report = ReportAdminTab()
        self.tabs.addTab(self.tab_report, "📊 使用率报表")

        # W12: Tab 5 用户人脸管理
        from src.ui.widgets.face_admin_tab import FaceAdminTab
        self.tab_face = FaceAdminTab()
        self.tabs.addTab(self.tab_face, "👤 人脸管理")

        # W14: 主布局 margin/spacing 加大, 让顶部信息条与 Tab 容器不挤
        main = QVBoxLayout()
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)
        main.addLayout(top)
        main.addWidget(self.tabs)
        self.setLayout(main)

    def closeEvent(self, event):
        """用户点 X 关窗时调用, 关闭可能打开的弹窗 (matplotlib canvas 等)."""
        for attr in ("task_detail_win", "lab_edit_win", "training_edit_win", "log_filter_win"):
            win = getattr(self, attr, None)
            if win is not None and hasattr(win, "close"):
                win.close()
        super().closeEvent(event)

    def _on_logout(self):
        ret = QMessageBox.question(self, "确认", "确定要退出登录吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            from src.ui.login_window import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()




