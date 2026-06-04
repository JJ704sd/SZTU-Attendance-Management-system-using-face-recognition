"""
ui/login_window.py — 登录窗口
- 支持登录 / 跳转到注册
- 登录成功后：根据 role 弹出对应主窗口（占位）
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QMessageBox, QComboBox, QGroupBox, QStatusBar,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.services.auth_service import AuthService, AuthError

log = logging.getLogger(__name__)


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.auth = AuthService()
        self.logged_user = None  # 登录成功后保存 User
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("智能考勤与实验室准入系统 — 登录")
        self.resize(420, 320)

        # 标题
        title = QLabel("智能考勤与实验室准入系统")
        title.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("深圳技术大学 · 健康与环境工程学院")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: gray;")

        # 表单
        form_box = QGroupBox("账号登录")
        form = QFormLayout()
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("用户名 / 学号")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.role_combo = QComboBox()
        self.role_combo.addItem("学生", "student")
        self.role_combo.addItem("教师", "teacher")
        self.role_combo.addItem("实验室管理员", "lab_admin")

        form.addRow("用户名:", self.username_edit)
        form.addRow("密码:", self.password_edit)
        form.addRow("角色:", self.role_combo)
        form_box.setLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        self.login_btn = QPushButton("登录")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._on_login)
        self.register_btn = QPushButton("注册新账号")
        self.register_btn.clicked.connect(self._on_register_clicked)
        self.quit_btn = QPushButton("退出")
        self.quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.register_btn)
        btn_layout.addWidget(self.quit_btn)

        # 状态栏（用 QLabel 模拟）
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet("color: gray; padding: 4px;")

        # 主布局
        main = QVBoxLayout()
        main.addWidget(title)
        main.addWidget(subtitle)
        main.addSpacing(10)
        main.addWidget(form_box)
        main.addLayout(btn_layout)
        main.addWidget(self.status_label)
        self.setLayout(main)

        # 回车触发登录
        self.password_edit.returnPressed.connect(self._on_login)

    # -----------------------------------------------------
    # 登录逻辑
    # -----------------------------------------------------
    def _on_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        role = self.role_combo.currentData()

        if not username or not password:
            QMessageBox.warning(self, "提示", "用户名和密码不能为空")
            return

        self._set_status("正在登录...")
        self.login_btn.setEnabled(False)
        try:
            user = self.auth.login(username, password)
            if user.role != role:
                QMessageBox.warning(
                    self, "角色不匹配",
                    f"该账号的角色是【{self._role_text(user.role)}】，请选择正确角色后重试。",
                )
                self._set_status("登录失败：角色不匹配")
                return
            self.logged_user = user
            self._set_status(f"登录成功：{user.real_name} ({user.role})")
            QMessageBox.information(
                self, "欢迎",
                f"欢迎，{user.real_name}！\n角色：{self._role_text(user.role)}",
            )
            # 根据 role 跳转到对应主窗口
            self._open_role_window(user)
        except AuthError as e:
            QMessageBox.warning(self, "登录失败", str(e))
            self._set_status(f"登录失败：{e}")
            self.password_edit.clear()
            self.password_edit.setFocus()
        except Exception as e:
            log.exception("登录异常")
            QMessageBox.critical(self, "异常", f"登录过程出现异常：\n{e}")
            self._set_status("登录异常")
        finally:
            self.login_btn.setEnabled(True)

    def _on_register_clicked(self):
        from src.ui.register_window import RegisterWindow
        self.register_win = RegisterWindow()
        self.register_win.show()
        self.hide()

    def _open_role_window(self, user):
        """登录成功，按角色打开主窗口并关闭登录窗口"""
        if user.role == "student":
            from src.ui.student_window import StudentWindow
            self.next_win = StudentWindow(user)
        elif user.role == "teacher":
            from src.ui.teacher_window import TeacherWindow
            self.next_win = TeacherWindow(user)
        elif user.role == "lab_admin":
            from src.ui.admin_window import AdminWindow
            self.next_win = AdminWindow(user)
        else:
            QMessageBox.critical(self, "异常", f"未知角色：{user.role}")
            return
        self.next_win.show()
        self.close()

    def _set_status(self, text: str):
        self.status_label.setText(text)

    @staticmethod
    def _role_text(role: str) -> str:
        return {"student": "学生", "teacher": "教师", "lab_admin": "实验室管理员"}.get(role, role)
