"""
ui/login_window.py — 登录窗口
- 支持登录 / 跳转到注册
- 登录成功后：根据 role 弹出对应主窗口（占位）
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QMessageBox, QComboBox, QGroupBox, QApplication,
)
from PyQt5.QtCore import Qt

from src.constants import ROLE_LABELS, ROLE_STUDENT, ROLE_TEACHER, ROLE_LAB_ADMIN
from src.services.auth_service import AuthService, AuthError
from src.ui.styles import apply_auth_style

log = logging.getLogger(__name__)


class LoginWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.auth = AuthService()
        self.logged_user = None  # 登录成功后保存 User
        self._init_ui()
        apply_auth_style(self)

    def _init_ui(self):
        self.setWindowTitle("智能考勤与实验室准入系统 — 登录")
        self.resize(440, 480)
        self.setMinimumWidth(400)

        # —— 品牌头部 ——
        header = QWidget()
        header.setObjectName("AuthHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 18)
        header_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        title = QLabel("智能考勤与实验室准入系统")
        title.setObjectName("AuthHeaderTitle")
        top_row.addWidget(title)
        top_row.addStretch()
        badge = QLabel("SZTU-HSEE")
        badge.setObjectName("AuthHeaderBadge")
        top_row.addWidget(badge)
        header_layout.addLayout(top_row)

        subtitle = QLabel("深圳技术大学 · 健康与环境工程学院")
        subtitle.setObjectName("AuthHeaderSubtitle")
        header_layout.addWidget(subtitle)

        # —— 表单 ——
        form_box = QGroupBox("账号登录")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setContentsMargins(16, 22, 16, 14)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("用户名 / 学号")
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.role_combo = QComboBox()
        self.role_combo.addItem(ROLE_LABELS[ROLE_STUDENT], ROLE_STUDENT)
        self.role_combo.addItem(ROLE_LABELS[ROLE_TEACHER], ROLE_TEACHER)
        self.role_combo.addItem(ROLE_LABELS[ROLE_LAB_ADMIN], ROLE_LAB_ADMIN)

        form.addRow("用户名", self.username_edit)
        form.addRow("密  码", self.password_edit)
        form.addRow("角  色", self.role_combo)
        form_box.setLayout(form)

        # —— 按钮 ——
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.login_btn = QPushButton("登 录")
        self.login_btn.setProperty("role", "primary")
        self.login_btn.setDefault(True)
        self.login_btn.clicked.connect(self._on_login)
        self.register_btn = QPushButton("注册新账号")
        self.register_btn.clicked.connect(self._on_register_clicked)
        self.quit_btn = QPushButton("退 出")
        self.quit_btn.setProperty("role", "danger")
        self.quit_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.login_btn, stretch=2)
        btn_layout.addWidget(self.register_btn, stretch=1)
        btn_layout.addWidget(self.quit_btn, stretch=1)

        # —— 状态栏 ——
        self.status_label = QLabel("就绪 — 请使用账号登录")
        self.status_label.setObjectName("status")
        self.status_label.setProperty("role", "status")

        # —— 主布局 ——
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(24, 22, 24, 18)
        body.setSpacing(14)
        body.addWidget(form_box)
        body.addLayout(btn_layout)
        body.addWidget(self.status_label)
        body.addStretch(1)
        outer.addLayout(body)

        # 窗口居中
        self._center_on_screen()

        # 回车触发登录
        self.password_edit.returnPressed.connect(self._on_login)

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

    # -----------------------------------------------------
    # 登录逻辑
    # -----------------------------------------------------
    def _on_login(self):
        username = self.username_edit.text().strip()
        password = self.password_edit.text()
        role = self.role_combo.currentData()

        if not username or not password:
            self._set_status("用户名和密码不能为空", state="error")
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
                self._set_status("登录失败：角色不匹配", state="error")
                return
            self.logged_user = user
            self._set_status(f"登录成功：{user.real_name}", state="success")
            QMessageBox.information(
                self, "欢迎",
                f"欢迎，{user.real_name}！\n角色：{self._role_text(user.role)}",
            )
            # 根据 role 跳转到对应主窗口
            self._open_role_window(user)
        except AuthError as e:
            QMessageBox.warning(self, "登录失败", str(e))
            self._set_status(f"登录失败：{e}", state="error")
            self.password_edit.clear()
            self.password_edit.setFocus()
        except Exception as e:
            log.exception("登录异常")
            QMessageBox.critical(self, "异常", f"登录过程出现异常：\n{e}")
            self._set_status("登录异常", state="error")
        finally:
            self.login_btn.setEnabled(True)

    def _on_register_clicked(self):
        from src.ui.register_window import RegisterWindow
        self.register_win = RegisterWindow()
        self.register_win.show()
        self.hide()

    def _open_role_window(self, user):
        """登录成功，按角色打开主窗口并关闭登录窗口"""
        if user.role == ROLE_STUDENT:
            from src.ui.student_window import StudentWindow
            self.next_win = StudentWindow(user)
        elif user.role == ROLE_TEACHER:
            from src.ui.teacher_window import TeacherWindow
            self.next_win = TeacherWindow(user)
        elif user.role == ROLE_LAB_ADMIN:
            from src.ui.admin_window import AdminWindow
            self.next_win = AdminWindow(user)
        else:
            QMessageBox.critical(self, "异常", f"未知角色：{user.role}")
            return
        self.next_win.show()
        self.close()

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        # 通过 dynamic property 切换颜色（GLOBAL_QSS 里 QLabel[role="status"][state=...]）
        self.status_label.setProperty("state", state)
        # 刷新样式
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    @staticmethod
    def _role_text(role: str) -> str:
        return ROLE_LABELS.get(role, role)
