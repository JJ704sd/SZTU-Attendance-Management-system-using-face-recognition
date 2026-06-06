"""
ui/register_window.py — 注册窗口
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

# 专业方向（5 个方向 + 兼容专业名「智能医学工程」）
DIRECTIONS = [
    "纳米医学技术",
    "生物医学仪器",
    "生物医学检测",
    "智能医疗仪器",
    "智能医疗信息",
    "智能医学工程",
]


class RegisterWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.auth = AuthService()
        self._init_ui()
        apply_auth_style(self)

    def _init_ui(self):
        self.setWindowTitle("注册新账号 — 智能考勤与实验室准入系统")
        self.resize(480, 600)
        self.setMinimumWidth(440)

        # —— 品牌头部（与登录窗同款）——
        header = QWidget()
        header.setObjectName("AuthHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(20, 16, 20, 18)
        header_layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        title = QLabel("注册新账号")
        title.setObjectName("AuthHeaderTitle")
        top_row.addWidget(title)
        top_row.addStretch()
        badge = QLabel("SZTU-HSEE")
        badge.setObjectName("AuthHeaderBadge")
        top_row.addWidget(badge)
        header_layout.addLayout(top_row)

        subtitle = QLabel("智能考勤与实验室准入系统")
        subtitle.setObjectName("AuthHeaderSubtitle")
        header_layout.addWidget(subtitle)

        # —— 表单 ——
        form_box = QGroupBox("账号信息")
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setContentsMargins(16, 22, 16, 14)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("3-50 位字母/数字/下划线")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setPlaceholderText("至少 6 位")
        self.password2_edit = QLineEdit()
        self.password2_edit.setEchoMode(QLineEdit.Password)
        self.password2_edit.setPlaceholderText("再输一次")
        self.real_name_edit = QLineEdit()
        self.real_name_edit.setPlaceholderText("请填写真实姓名")
        self.role_combo = QComboBox()
        self.role_combo.addItem(ROLE_LABELS[ROLE_STUDENT], ROLE_STUDENT)
        self.role_combo.addItem(ROLE_LABELS[ROLE_TEACHER], ROLE_TEACHER)
        self.role_combo.addItem(ROLE_LABELS[ROLE_LAB_ADMIN], ROLE_LAB_ADMIN)
        self.student_id_edit = QLineEdit()
        self.student_id_edit.setPlaceholderText("学生必填")
        self.direction_combo = QComboBox()
        self.direction_combo.addItem("（不填）", None)
        for d in DIRECTIONS:
            self.direction_combo.addItem(d, d)
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("可选")
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("可选")

        form.addRow("用户名 *", self.username_edit)
        form.addRow("密码 *", self.password_edit)
        form.addRow("确认密码 *", self.password2_edit)
        form.addRow("真实姓名 *", self.real_name_edit)
        form.addRow("角色 *", self.role_combo)
        form.addRow("学号", self.student_id_edit)
        form.addRow("专业方向", self.direction_combo)
        form.addRow("邮箱", self.email_edit)
        form.addRow("电话", self.phone_edit)
        form_box.setLayout(form)

        # 角色变化时联动学号/方向是否必填
        self.role_combo.currentIndexChanged.connect(self._on_role_changed)
        self._on_role_changed()

        # —— 按钮 ——
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.submit_btn = QPushButton("提 交 注 册")
        self.submit_btn.setProperty("role", "primary")
        self.submit_btn.clicked.connect(self._on_submit)
        self.back_btn = QPushButton("返 回 登 录")
        self.back_btn.clicked.connect(self._on_back)
        btn_layout.addWidget(self.submit_btn, stretch=2)
        btn_layout.addWidget(self.back_btn, stretch=1)

        # —— 状态栏 ——
        self.status_label = QLabel("提示：带 * 为必填项；学生需填学号与专业方向")
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

        self._center_on_screen()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

    def _on_role_changed(self):
        role = self.role_combo.currentData()
        if role == ROLE_STUDENT:
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
                self._set_status("请填写所有带 * 的必填项", state="error")
                QMessageBox.warning(self, "提示", "请填写所有带 * 的必填项")
                return
            if password != password2:
                self._set_status("两次密码不一致", state="error")
                QMessageBox.warning(self, "提示", "两次密码不一致")
                return

            self.auth.register(
                username=username, password=password, real_name=real_name, role=role,
                student_id=student_id, direction=direction, email=email, phone=phone,
            )
            self._set_status(f"账号 {username} 注册成功，请返回登录", state="success")
            QMessageBox.information(self, "注册成功", f"账号 {username} 注册成功！请返回登录。")
            self._on_back()
        except AuthError as e:
            self._set_status(f"注册失败：{e}", state="error")
            QMessageBox.warning(self, "注册失败", str(e))
        except Exception as e:
            log.exception("注册异常")
            self._set_status("注册异常", state="error")
            QMessageBox.critical(self, "异常", f"注册过程出现异常：\n{e}")

    def _on_back(self):
        from src.ui.login_window import LoginWindow
        self.login_win = LoginWindow()
        self.login_win.show()
        self.close()

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
