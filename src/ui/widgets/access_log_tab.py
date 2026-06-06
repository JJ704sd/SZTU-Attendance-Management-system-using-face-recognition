"""
ui/widgets/access_log_tab.py — 实验室管理员 Tab 3「准入日志」

W4 Phase 5c: lab_access_log 只读查询 UI
- QTableWidget 列表（不可编辑）
- 工具栏: 实验室下拉 / 通过/拒绝筛选 / 刷新
"""
import logging
from datetime import datetime, timedelta

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from src.dao.lab_access_log_dao import LabAccessLogDao
from src.dao.lab_dao import LabDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.lab import LabAccessLog

log = logging.getLogger(__name__)

# 筛选选项
GRANTED_FILTER = [
    ("全部", None),
    ("✅ 放行", 1),
    ("❌ 拒绝", 0),
]
DEFAULT_LIMIT = 200


class AccessLogTab(QWidget):
    """Tab 3 准入日志。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("实验室:"))
        self.lab_combo = QComboBox()
        self.lab_combo.addItem("全部", None)
        with session_scope() as s:
            labs = LabDao(s).find_all()
        for l in labs:
            self.lab_combo.addItem(f"#{l.id} {l.name}", l.id)
        toolbar.addWidget(self.lab_combo)

        toolbar.addWidget(QLabel("结果:"))
        self.granted_combo = QComboBox()
        for label, value in GRANTED_FILTER:
            self.granted_combo.addItem(label, value)
        toolbar.addWidget(self.granted_combo)

        toolbar.addWidget(QLabel("近:"))
        self.days_combo = QComboBox()
        self.days_combo.addItem("24 小时", 1)
        self.days_combo.addItem("7 天", 7)
        self.days_combo.addItem("30 天", 30)
        self.days_combo.addItem("90 天", 90)
        self.days_combo.setCurrentIndex(1)  # 默认 7 天
        toolbar.addWidget(self.days_combo)

        toolbar.addStretch()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "时间", "学生", "实验室", "结果", "原因"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # 状态
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status")
        self.status_label.setProperty("role", "status")
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        # 工具栏筛选变更自动刷新
        self.lab_combo.currentIndexChanged.connect(self.refresh)
        self.granted_combo.currentIndexChanged.connect(self.refresh)
        self.days_combo.currentIndexChanged.connect(self.refresh)

    def refresh(self):
        """根据工具栏筛选重载日志列表。"""
        lab_id = self.lab_combo.currentData()
        granted = self.granted_combo.currentData()
        days = self.days_combo.currentData()
        since = datetime.now() - timedelta(days=days)

        with session_scope() as s:
            q = s.query(LabAccessLog).filter(
                LabAccessLog.access_time >= since,
            )
            if lab_id is not None:
                q = q.filter(LabAccessLog.lab_id == lab_id)
            if granted is not None:
                q = q.filter(LabAccessLog.granted == granted)
            logs = q.order_by(LabAccessLog.access_time.desc()).limit(DEFAULT_LIMIT).all()

            # 查 student / lab 名字
            student_ids = {l.student_id for l in logs if l.student_id is not None}
            lab_ids = {l.lab_id for l in logs}
            students = {u.id: u for u in UserDao(s).find_by_role("student")}
            labs = {lab.id: lab for lab in LabDao(s).find_all()}

        self.table.setRowCount(len(logs))
        for i, log_entry in enumerate(logs):
            stu = students.get(log_entry.student_id) if log_entry.student_id else None
            lab = labs.get(log_entry.lab_id)

            self.table.setItem(i, 0, QTableWidgetItem(str(log_entry.id)))
            self.table.setItem(i, 1, QTableWidgetItem(
                log_entry.access_time.strftime("%Y-%m-%d %H:%M:%S")
                if log_entry.access_time else "—"
            ))
            if stu:
                stu_text = f"#{stu.id} {stu.real_name}"
            else:
                stu_text = "—"
            self.table.setItem(i, 2, QTableWidgetItem(stu_text))
            self.table.setItem(i, 3, QTableWidgetItem(
                f"#{lab.id} {lab.name}" if lab else f"#{log_entry.lab_id}"
            ))

            # 结果列：放行绿、拒绝红
            if log_entry.granted == 1:
                result_text = "✅ 放行"
                color_hex = "#16A34A"  # 绿
            else:
                result_text = "❌ 拒绝"
                color_hex = "#DC2626"  # 红
            result_item = QTableWidgetItem(result_text)
            result_item.setForeground(QColor(color_hex))
            self.table.setItem(i, 4, result_item)

            self.table.setItem(i, 5, QTableWidgetItem(
                log_entry.reason or "—"
            ))

        self._set_status(
            f"已加载 {len(logs)} 条准入日志（近 {days} 天{f'，实验室 #{lab_id}' if lab_id else ''}{'，放行' if granted == 1 else '拒绝' if granted == 0 else ''}）"
        )

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
