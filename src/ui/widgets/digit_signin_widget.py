"""
ui/widgets/digit_signin_widget.py — 学生端「数字码签到」子 Tab

W13+ 数字码签到方式 UI:
  - QLineEdit (maxLength=4, QIntValidator(0, 9999)) 接 4 位数字
  - QPushButton("签到") 提交到 attendance_service.sign_in_by_digit
  - 成功 → 状态 label 显示「✅ 出勤 / ⚠️ 迟到」(根据 record.status),
          发 signal signin_succeeded 给父窗口（让父窗口 disable 其他子 Tab）
  - 失败 → 状态 label 显示「❌ 签到码无效或已过期」(红色), 不弹 QMessageBox

设计要点:
  - 数字码由教师端 generate_signin_code(task_id, 'digit') 生成, 60s TTL.
  - 学生只负责「输入 + 提交」, 业务规则（present/late/重复拦截）全在 service 层.
  - 整个 widget 自包含, 父窗口 (StudentWindow) 只需构造时传 task_id/user_id/service,
    不用知道细节. 信号 signin_succeeded 通知父窗口统一更新状态.
"""
import logging
from typing import Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
)

from src.services.attendance_service import AttendanceService

log = logging.getLogger(__name__)

# 状态展示文案（跟 student_window.py STATUS_DISPLAY 对齐，保持一致 UX）
_STATUS_TEXT = {
    "present": "✅ 出勤",
    "late":    "⚠️ 迟到",
}


class DigitSigninWidget(QWidget):
    """学生端「数字码签到」子 Tab 控件.

    构造参数:
        parent:              父窗口（一般传 StudentWindow）
        task_id:             当前选中的考勤任务 id
        user_id:             当前登录学生 id
        attendance_service:  业务服务实例

    Signals:
        signin_succeeded(record): 签到成功, 携带 AttendanceRecord（已 expunge）
                                   父窗口可 disable 其他子 Tab, 刷新任务下拉等
    """

    signin_succeeded = pyqtSignal(object)  # AttendanceRecord

    def __init__(self, parent: QWidget,
                 task_id: int,
                 user_id: int,
                 attendance_service: AttendanceService):
        super().__init__(parent)
        self._task_id = task_id
        self._user_id = user_id
        self._attendance_service = attendance_service

        self._init_ui()
        # 自动聚焦到输入框 —— 学生打开就能敲 4 位数字
        self.code_edit.setFocus()

    def _init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)

        # 提示文字
        hint = QLabel("🔢 请输入 4 位数字签到码")
        hint.setStyleSheet("font-size: 14px; font-weight: bold; color: #1F2937;")
        layout.addWidget(hint)

        sub_hint = QLabel(
            f"向教师询问当前 4 位数字码（60 秒内有效）\n任务 ID: #{self._task_id}"
        )
        sub_hint.setStyleSheet("color: #6B7280; font-size: 12px;")
        sub_hint.setWordWrap(True)
        layout.addWidget(sub_hint)

        # 输入行
        input_row = QHBoxLayout()
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("例如: 0423")
        self.code_edit.setMaxLength(4)                              # 超过自动截断
        self.code_edit.setValidator(QIntValidator(0, 9999, self))  # 只允许 0-9999
        self.code_edit.setAlignment(Qt.AlignCenter)
        # 数字码字体放大、加粗
        f = self.code_edit.font()
        f.setPointSize(24)
        f.setBold(True)
        self.code_edit.setFont(f)
        self.code_edit.setMinimumWidth(160)
        self.code_edit.setMaximumWidth(200)
        self.code_edit.returnPressed.connect(self._on_submit)  # 回车直接提交
        input_row.addWidget(self.code_edit)

        self.submit_btn = QPushButton("签到")
        self.submit_btn.setProperty("role", "primary")
        self.submit_btn.setMinimumWidth(100)
        self.submit_btn.clicked.connect(self._on_submit)
        input_row.addWidget(self.submit_btn)

        layout.addLayout(input_row)

        # 状态
        self.status_label = QLabel("等待输入...")
        self.status_label.setProperty("role", "status")
        self.status_label.setWordWrap(True)
        self.status_label.setMinimumHeight(40)
        layout.addWidget(self.status_label)

        layout.addStretch()
        self.setLayout(layout)

    def _on_submit(self):
        """点击「签到」或回车触发."""
        code_value = self.code_edit.text().strip()
        if not code_value:
            self._set_status("⚠️ 请先输入 4 位数字码", "error")
            self.code_edit.setFocus()
            return

        # 防御性: maxLength + validator 已经拦了非数字/超长, 但补一层
        if len(code_value) != 4 or not code_value.isdigit():
            self._set_status("❌ 签到码格式错误（必须是 4 位数字）", "error")
            return

        # 业务调用 (service 内部会: 验证码 + 校验 task+user+重复拦截 + 写记录)
        try:
            record = self._attendance_service.sign_in_by_digit(
                self._task_id, self._user_id, code_value,
            )
        except Exception as e:
            log.exception("数字码签到异常")
            self._set_status(f"❌ 签到异常：{e}", "error")
            return

        if record is None:
            # None = 码无效 / 已过期 / 已签到 / 任务已关闭（service 不区分）
            self._set_status("❌ 签到码无效或已过期", "error")
            return

        # 成功 → 状态文案 + signal 给父窗口
        text = _STATUS_TEXT.get(record.status, f"✅ 签到成功（{record.status}）")
        self._set_status(text, "success")
        # 锁住输入框, 防止重复提交
        self.code_edit.setEnabled(False)
        self.submit_btn.setEnabled(False)
        # 给父窗口一个更新其他子 Tab 的机会
        self.signin_succeeded.emit(record)

    def _set_status(self, text: str, state: str):
        """state: 'neutral' / 'success' / 'error' —— 跟 styles.py QSS 约定一致."""
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        # 刷新 QSS state 选择器
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    # ------------------ 父窗口辅助 ------------------
    def reset_for_new_task(self, task_id: int):
        """父窗口切换 task 时调用, 重置 widget 状态 (解锁输入框 + 清空)."""
        self._task_id = task_id
        self.code_edit.setEnabled(True)
        self.submit_btn.setEnabled(True)
        self.code_edit.clear()
        self._set_status(f"已切换到任务 #{task_id}，请输入新码", "neutral")
        self.code_edit.setFocus()
