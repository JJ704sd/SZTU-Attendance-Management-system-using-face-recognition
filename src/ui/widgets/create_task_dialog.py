"""
ui/widgets/create_task_dialog.py — 发起考勤对话框
"""
from datetime import datetime
from PyQt5.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QDateTimeEdit, QDialogButtonBox,
    QMessageBox, QVBoxLayout, QLabel,
)
from PyQt5.QtCore import QDateTime

from src.db import session_scope
from src.dao.course_dao import CourseDao
from src.dao.classroom_dao import ClassroomDao
from src.services.attendance_service import AttendanceService
from src.models.user import User


class CreateTaskDialog(QDialog):
    def __init__(self, teacher: User, parent=None):
        super().__init__(parent)
        self.teacher = teacher
        self.attendance = AttendanceService()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("发起新考勤")
        self.setModal(True)
        # W14+ 演示模式: 窗口 +60x60
        self.resize(480, 340)

        layout = QVBoxLayout()
        intro = QLabel("填写以下信息创建考勤任务：")
        intro.setStyleSheet("color: gray;")
        layout.addWidget(intro)

        form = QFormLayout()

        # 课程下拉（只显示该教师教的）
        self.course_combo = QComboBox()
        with session_scope() as s:
            cdao = CourseDao(s)
            self.courses = cdao.find_by_teacher(self.teacher.id)
        if not self.courses:
            self.course_combo.addItem("（暂无可授课程，请先在数据库添加）", None)
        else:
            for c in self.courses:
                label = f"[{c.course_type}] {c.course_code} {c.course_name}"
                self.course_combo.addItem(label, c.id)
        form.addRow("课程*:", self.course_combo)

        # 教室下拉
        self.room_combo = QComboBox()
        with session_scope() as s:
            rdao = ClassroomDao(s)
            self.rooms = rdao.find_all()
        for r in self.rooms:
            self.room_combo.addItem(f"{r.name}（{r.location or '—'}）", r.id)
        form.addRow("教室*:", self.room_combo)

        # 时间 (默认 now + 45 min)
        now = datetime.now()
        self.start_edit = QDateTimeEdit(QDateTime.fromString(
            now.strftime("%Y-%m-%d %H:%M"), "yyyy-MM-dd HH:mm"))
        self.start_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.start_edit.setCalendarPopup(True)

        self.end_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(45 * 60))
        self.end_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.end_edit.setCalendarPopup(True)

        form.addRow("开始时间*:", self.start_edit)
        form.addRow("结束时间*:", self.end_edit)
        layout.addLayout(form)

        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("创建")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._on_submit)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self.setLayout(layout)

    def _on_submit(self):
        course_id = self.course_combo.currentData()
        room_id = self.room_combo.currentData()
        start = self.start_edit.dateTime().toPyDateTime()
        end = self.end_edit.dateTime().toPyDateTime()

        if not course_id:
            QMessageBox.warning(self, "提示", "请先在数据库里给该教师添加课程")
            return
        if not room_id:
            QMessageBox.warning(self, "提示", "请选择教室")
            return
        if end <= start:
            QMessageBox.warning(self, "提示", "结束时间必须晚于开始时间")
            return

        try:
            tid = self.attendance.create_task(
                course_id=course_id,
                teacher_id=self.teacher.id,
                classroom_id=room_id,
                start_time=start,
                end_time=end,
            )
            QMessageBox.information(self, "成功", f"任务 #{tid} 已创建")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "提示", str(e))
        except Exception as e:
            QMessageBox.critical(self, "失败", f"创建失败：{e}")
