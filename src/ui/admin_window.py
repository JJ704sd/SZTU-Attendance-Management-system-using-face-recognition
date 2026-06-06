"""
ui/admin_window.py — 实验室管理员端主窗口

W4 Phase 5 接入进度:
- ✅ Tab 1 实验室管理: CRUD（Phase 5a 完成）
- ✅ Tab 2 安全培训录入: CRUD（Phase 5b完成）
- ✅ Tab 3 准入日志: 只读 + 筛选（Phase 5c完成）
- ✅ Tab 4 使用率报表: matplotlib 嵌入 + 4 类图表切换（Phase 5d完成）

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
        self.resize(1100, 700)  # 加宽以容纳 matplotlib 图表

        top = QHBoxLayout()
        welcome = QLabel(f"欢迎，{self.user.real_name}{welcome_suffix(self.user)}")
        f = QFont(); f.setPointSize(12); f.setBold(True)
        welcome.setFont(f)
        top.addWidget(welcome)
        top.addStretch()
        top.addWidget(QLabel(f"用户名: {self.user.username} | 角色: 实验室管理员"))
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        self.tabs = QTabWidget()
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

        main = QVBoxLayout()
        main.addLayout(top)
        main.addWidget(self.tabs)
        self.setLayout(main)

    def _on_logout(self):
        ret = QMessageBox.question(self, "确认", "确定要退出登录吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            from src.ui.login_window import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()




