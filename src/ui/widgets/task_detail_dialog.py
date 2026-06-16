"""
ui/widgets/task_detail_dialog.py — 任务详情对话框
显示某个考勤任务的所有学生签到情况
"""
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView,
)
from PyQt5.QtGui import QFont

from src.db import session_scope
from src.dao.attendance_dao import AttendanceTaskDao, AttendanceRecordDao
from src.dao.user_dao import UserDao
from src.dao.course_dao import CourseDao
from src.dao.classroom_dao import ClassroomDao


class TaskDetailDialog(QDialog):
    def __init__(self, task_id: int, parent=None):
        super().__init__(parent)
        self.task_id = task_id
        self._init_ui()
        self._load()

    def _init_ui(self):
        self.setWindowTitle(f"任务 #{self.task_id} 签到详情")
        # W14+ 演示模式: 窗口 +160x100, 表格更舒展
        self.resize(880, 600)

        self.title_label = QLabel("加载中...")
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        self.title_label.setStyleSheet("padding: 8px;")

        self.summary_label = QLabel("")
        self.summary_label.setStyleSheet("color: gray; padding: 4px;")

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["学号", "姓名", "签到时间", "状态", "匹配距离"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(close_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.table)
        layout.addLayout(btn_row)
        self.setLayout(layout)

    def _load(self):
        with session_scope() as s:
            tdao = AttendanceTaskDao(s)
            task = tdao.find_by_id(self.task_id)
            if not task:
                self.title_label.setText(f"任务 #{self.task_id} 不存在")
                return

            cdao = CourseDao(s)
            rdao = ClassroomDao(s)
            course = cdao.get(task.course_id)
            room = rdao.get(task.classroom_id)

            rec_dao = AttendanceRecordDao(s)
            user_dao = UserDao(s)
            records = rec_dao.find_by_task(self.task_id)
            users = {u.id: u for u in user_dao.find_by_role("student")}

        # 标题
        self.title_label.setText(
            f"任务 #{task.id} — {course.course_name if course else '?'} @ {room.name if room else '?'} "
            f"({task.start_time:%Y-%m-%d %H:%M} ~ {task.end_time:%H:%M})"
        )

        # 汇总
        from collections import Counter
        counter = Counter(r.status for r in records)
        total = sum(counter.values())
        self.summary_label.setText(
            f"总人数: {total} | "
            f"出勤: {counter.get('present', 0)} | "
            f"迟到: {counter.get('late', 0)} | "
            f"请假: {counter.get('leave', 0)} | "
            f"缺勤: {counter.get('absent', 0)}"
        )

        # 表格
        self.table.setRowCount(len(records))
        status_text = {
            "present": "✅ 出勤",
            "late": "⚠️ 迟到",
            "absent": "❌ 缺勤",
            "leave": "📝 请假",
        }
        for i, r in enumerate(records):
            u = users.get(r.student_id)
            self.table.setItem(i, 0, QTableWidgetItem(u.student_id if u else str(r.student_id)))
            self.table.setItem(i, 1, QTableWidgetItem(u.real_name if u else f"#{r.student_id}"))
            self.table.setItem(i, 2, QTableWidgetItem(
                r.sign_in_time.strftime("%Y-%m-%d %H:%M:%S") if r.sign_in_time else "—"
            ))
            self.table.setItem(i, 3, QTableWidgetItem(status_text.get(r.status, r.status)))
            self.table.setItem(i, 4, QTableWidgetItem(
                f"{r.match_score:.4f}" if r.match_score is not None else "—"
            ))
