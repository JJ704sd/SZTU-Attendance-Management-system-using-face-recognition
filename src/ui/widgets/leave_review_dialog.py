"""
ui/widgets/leave_review_dialog.py — 请假审批对话框 (W6 Phase 1)
老师查看所有 open 任务下的待审批请假, 批/驳一键完成。
"""
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QMessageBox,
)

from src.db import session_scope
from src.dao.user_dao import UserDao
from src.services.leave_service import LeaveError, LeaveService


class LeaveReviewDialog(QDialog):
    def __init__(self, approver, parent=None):
        """approver: User 对象 (role=teacher 或 lab_admin)。"""
        super().__init__(parent)
        self.approver = approver
        self.setWindowTitle("📝 待审批请假")
        self.resize(820, 480)
        self._init_ui()
        self._load()

    def _init_ui(self):
        self.info_label = QLabel("查看所有 open 任务的待审批请假申请, 双击行可批准/拒绝")
        self.info_label.setStyleSheet("color: gray; padding: 4px;")

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["请假ID", "任务ID", "学号", "姓名", "原因", "申请时间"]
        )
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        # 双击某行 → 弹批/驳
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # 工具栏
        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self._load)
        self.approve_btn = QPushButton("✅ 批准选中")
        self.approve_btn.clicked.connect(lambda: self._review_selected(True))
        self.reject_btn = QPushButton("❌ 拒绝选中")
        self.reject_btn.clicked.connect(lambda: self._review_selected(False))
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.approve_btn)
        toolbar.addWidget(self.reject_btn)
        toolbar.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        toolbar.addWidget(self.close_btn)

        layout = QVBoxLayout()
        layout.addWidget(self.info_label)
        layout.addLayout(toolbar)
        layout.addWidget(self.table)
        self.setLayout(layout)

    def _load(self):
        """查该老师所有 open 任务下的待审批请假。"""
        from src.dao.attendance_dao import AttendanceTaskDao
        from src.models.attendance import LeaveRequest
        from sqlalchemy import and_

        with session_scope() as s:
            tdao = AttendanceTaskDao(s)
            my_open_tasks = tdao.find_open_tasks_for_teacher(self.approver.id)
            task_ids = [t.id for t in my_open_tasks]
            if not task_ids:
                self.table.setRowCount(0)
                return

            # 查这些任务下的所有 pending
            reqs = s.query(LeaveRequest).filter(
                and_(
                    LeaveRequest.task_id.in_(task_ids),
                    LeaveRequest.status == "pending",
                )
            ).all()
            user_ids = list({r.student_id for r in reqs})
            users = {u.id: u for u in s.query(UserDao(s).model).filter(
                UserDao(s).model.id.in_(user_ids)
            ).all()} if user_ids else {}

        self.table.setRowCount(len(reqs))
        for i, r in enumerate(reqs):
            u = users.get(r.student_id)
            self.table.setItem(i, 0, QTableWidgetItem(str(r.id)))
            self.table.setItem(i, 1, QTableWidgetItem(f"#{r.task_id}"))
            self.table.setItem(i, 2, QTableWidgetItem(u.student_id if u else str(r.student_id)))
            self.table.setItem(i, 3, QTableWidgetItem(u.real_name if u else f"#{r.student_id}"))
            self.table.setItem(i, 4, QTableWidgetItem(r.reason or ""))
            self.table.setItem(
                i, 5,
                QTableWidgetItem(r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—")
            )
            # 整行背景色
            for col in range(6):
                item = self.table.item(i, col)
                if item:
                    item.setBackground(QColor("#FEF3C7"))  # 淡黄

    def _selected_request_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        # W11: 加 try/except 防 item.text() 异常
        try:
            return int(item.text())
        except (ValueError, TypeError):
            return None

    def _on_cell_double_clicked(self, row, col):
        req_id = self._selected_request_id()
        if req_id is None:
            return
        # 双击行 → 弹批/驳确认
        reason = self.table.item(row, 4).text() if self.table.item(row, 4) else ""
        from PyQt5.QtWidgets import QInputDialog
        comment, ok = QInputDialog.getText(
            self, f"审批 #{req_id}", f"原因: {reason}\n审批意见 (可空):"
        )
        if not ok:
            return
        ret = QMessageBox.question(
            self, "审批", f"请假 #{req_id}\n原因: {reason}\n\n批准吗?",
            QMessageBox.Yes | QMessageBox.No,
        )
        approve = (ret == QMessageBox.Yes)
        self._do_review(req_id, approve, comment)

    def _review_selected(self, approve: bool):
        req_id = self._selected_request_id()
        if req_id is None:
            QMessageBox.information(self, "提示", "请先选中一行")
            return
        self._do_review(req_id, approve, "")

    def _do_review(self, req_id: int, approve: bool, comment: str):
        try:
            LeaveService().teacher_review(
                req_id, self.approver.id, approve=approve, comment=comment or None,
            )
            verb = "批准" if approve else "拒绝"
            QMessageBox.information(self, "完成", f"请假 #{req_id} 已{verb}")
            self._load()
        except LeaveError as e:
            QMessageBox.warning(self, "审批失败", str(e))
