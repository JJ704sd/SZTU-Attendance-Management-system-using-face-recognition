"""
ui/register_window.py — 注册窗口
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QMessageBox, QComboBox, QGroupBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.services.auth_service import AuthService, AuthError

log = logging.getLogger(__name__)

# 5 个专业方向
DIRECTIONS = [
    "纳米医学技术",
    "生物医学仪器",
    "生物医学检测",
    "智能医疗仪器",
    "智能医疗信息",
]


class RegisterWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.auth = AuthService()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("注册新账号")
        self.resize(440, 480)

        title = QLabel("注册新账号")
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)

        form_box = QGroupBox("账号信息")
        form = QFormLayout()

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("3-50 位字母/数字/下划线")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("至少 6 位")
        self.password2_edit = QLineEdit()
        self.password2_edit.setEchoMode(QLineEdit.Password)
        self.password2_edit.setPlaceholderText("再输一次")
        self.real_name_edit = QLineEdit()
        self.role_combo = QComboBox()
        self.role_combo.addItem("学生", "student")
        self.role_combo.addItem("教师", "teacher")
        self.role_combo.addItem("实验室管理员", "lab_admin")
        self.student_id_edit = QLineEdit()
        self.student_id_edit.setPlaceholderText("学生必填")
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("（不填）", None)
        for d in DIRECTIONS:
            self.direction_combo.addItem(d, d)
        self.email_edit = QLineEdit()
        self.phone_edit = QLineEdit()

        form.addRow("用户名*:", self.username_edit)
        form.addRow("密码*:", self.password_edit)
        form.addRow("确认密码*:", self.password2_edit)
        form.addRow("真实姓名*:", self.real_name_edit)
        form.addRow("角色*:", self.role_combo)
        form.addRow("学号:", self.student_id_edit)
        form.addRow("专业方向:", self.direction_combo)
        form.addRow("邮箱:", self.email_edit)
        form.addRow("电话:", self.phone_edit)
        form_box.setLayout(form)

        # 角色变化时联动学号/方向是否必填
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        self._on_role_changed()

        # 按钮
        btn_layout = QHBoxLayout()
        self.submit_btn = QPushButton("提交注册")
        self.submit_btn.clicked.connect(self._on_submit)
        self.back_btn = QPushButton("返回登录")
        self.back_btn.clicked.connect(self._on_back)
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.back_btn)

        self.status_label = QLabel("提示：带 * 为必填项")
        self.status_label.setStyleSheet("color: gray; padding: 4px;")

        main = QVBoxLayout()
        main.addWidget(title)
        main.addWidget(form_box)
        main.addLayout(btn_layout)
        main.addWidget(self.status_label)
        self.setLayout(main)

    def _on_role_changed(self):
        role = self.role_combo.currentData()
        if role == "student":
            self.student_id_edit.setPlaceholderText("学生必填")
            self.direction_combo.setEnabled(True)
        else:
            self.student_id_edit.setPlaceholderText("非学生可不填")
            self.direction_combo.setEnabled(False)
            self.direction_combo.setCurrentIndex(0)

    def _on_submit(self):
        try:
            username = self.username_edit.text().strip()
            password = self.password_edit.text()
            password2 = self.password2_edit.text()
            real_name = self.real_name_edit.text().strip()
            role = self.role_combo.currentData()
            student_id = self.student_id_edit.text().strip() or None
            direction = self.direction_combo.currentData()
            email = self.email_edit.text().strip() or None
            phone = self.phone_edit.text().strip() or None

            if not (username and password and real_name):
                QMessageBox.warning(self, "提示", "请填写所有带 * 的必填项")
                return
            if password != password2:
                QMessageBox.warning(self, "提示", "两次密码不一致")
                return

            self.auth.register(
                username=username, password=password, real_name=real_name, role=role,
                student_id=student_id, direction=direction, email=email, phone=phone,
            )
            QMessageBox.information(self, "注册成功", f"账号 {username} 注册成功！请返回登录。")
            self._on_back()
        except AuthError as e:
            QMessageBox.warning(self, "注册失败", str(e))
        except Exception as e:
            log.exception("注册异常")
            QMessageBox.critical(self, "异常", f"注册过程出现异常：\n{e}")

    def _on_back(self):
        from src.ui.login_window import LoginWindow
        self.login_win = LoginWindow()
        self.login_win.show()
        self.close()
