"""
ui/admin_window.py — 实验室管理员端主窗口（占位，待 W4 完整接入）
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QTabWidget,
)
from PyQt5.QtGui import QFont

from src.models.user import User

log = logging.getLogger(__name__)


class AdminWindow(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"实验室管理员端 — {self.user.real_name}")
        self.resize(900, 600)

        top = QHBoxLayout()
        welcome = QLabel(f"欢迎，{self.user.real_name} 管理员")
        f = QFont(); f.setPointSize(12); f.setBold(True)
        welcome.setFont(f)
        top.addWidget(welcome)
        top.addStretch()
        top.addWidget(QLabel(f"用户名: {self.user.username} | 角色: 实验室管理员"))
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        tabs = QTabWidget()
        tabs.addTab(self._placeholder("🏛 实验室管理", "W4 接入：CRUD 实验室信息"), "实验室管理")
        tabs.addTab(self._placeholder("📋 安全培训录入", "W4 接入：录入学生培训记录"), "安全培训")
        tabs.addTab(self._placeholder("🚪 准入日志", "W4 接入：实时查看准入记录"), "准入日志")
        tabs.addTab(self._placeholder("📊 使用率报表", "W4 接入：matplotlib 报表"), "使用率报表")

        main = QVBoxLayout()
        main.addLayout(top)
        main.addWidget(tabs)
        self.setLayout(main)

    def _placeholder(self, title: str, desc: str) -> QWidget:
        from PyQt5.QtCore import Qt
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        lbl = QLabel(f"{title}\n\n{desc}")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("color: gray; font-size: 14px; padding: 40px;")
        layout.addWidget(lbl)
        page.setLayout(layout)
        return page

    def _on_logout(self):
        ret = QMessageBox.question(self, "确认", "确定要退出登录吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            from src.ui.login_window import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()
