"""
ui/student_window.py — 学生端主窗口（占位，待 W3 接入人脸注册/签到）
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QTabWidget,
)
from PyQt5.QtGui import QFont

from src.models.user import User

log = logging.getLogger(__name__)


class StudentWindow(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"学生端 — {self.user.real_name}")
        self.resize(820, 560)

        top = QHBoxLayout()
        welcome = QLabel(f"欢迎，{self.user.real_name} 同学")
        f = QFont(); f.setPointSize(12); f.setBold(True)
        welcome.setFont(f)
        top.addWidget(welcome)
        top.addStretch()
        info = QLabel(f"学号: {self.user.student_id or '—'} | 方向: {self.user.direction or '—'}")
        info.setStyleSheet("color: gray;")
        top.addWidget(info)
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        tabs = QTabWidget()
        tabs.addTab(self._placeholder("📷 人脸注册", "W3 接入：摄像头采集 30 张 + 编码入库"), "人脸注册")
        tabs.addTab(self._placeholder("✅ 签到", "W3 接入：刷脸签到/查看历史考勤"), "签到")
        tabs.addTab(self._placeholder("🏫 我的实验室", "W4 接入：查看准入记录/培训状态"), "我的实验室")
        tabs.addTab(self._placeholder("📝 请假申请", "W4 接入：请假表单"), "请假申请")

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
