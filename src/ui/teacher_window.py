"""
ui/teacher_window.py — 教师端主窗口
布局：顶部信息条 + 4 个 Tab
- 发起考勤：调用 CreateTaskDialog
- 历史考勤：QTableView 显示该教师所有任务，点击看详情
- 统计报表：占位（W4 做）
- 账号：显示当前用户信息 + 修改密码
"""
import logging
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QAbstractItemView,
    QGroupBox, QFormLayout, QLineEdit, QDialog,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

from src.db import session_scope
from src.dao.attendance_dao import AttendanceTaskDao
from src.dao.course_dao import CourseDao
from src.dao.classroom_dao import ClassroomDao
from src.services.attendance_service import AttendanceService
from src.services.auth_service import AuthService, AuthError
from src.models.user import User
from src.ui.styles import welcome_suffix

log = logging.getLogger(__name__)


class TeacherWindow(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user  # 已登录的教师 User
        self.attendance = AttendanceService()
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"教师端 — {self.user.real_name}")
        self.resize(900, 600)

        # 顶部
        top = QHBoxLayout()
        welcome = QLabel(f"欢迎，{self.user.real_name}{welcome_suffix(self.user)}")
        welcome_font = QFont()
        welcome_font.setPointSize(12)
        welcome_font.setBold(True)
        welcome.setFont(welcome_font)
        top.addWidget(welcome)
        top.addStretch()
        info = QLabel(f"用户名: {self.user.username} | 角色: 教师")
        info.setStyleSheet("color: gray;")
        top.addWidget(info)
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        # Tab
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_create_tab(), "发起考勤")
        self.tabs.addTab(self._build_history_tab(), "历史考勤")
        self.tabs.addTab(self._build_report_tab(), "统计报表")
        self.tabs.addTab(self._build_account_tab(), "账号")

        # 主布局
        main = QVBoxLayout()
        main.addLayout(top)
        main.addWidget(self.tabs)
        self.setLayout(main)

        # 启动时刷新一次历史
        self._refresh_history()

    # =====================================================
    # Tab 1: 发起考勤
    # =====================================================
    def _build_create_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        intro = QLabel("点击下方按钮创建一个新的考勤任务。\n任务创建后保持 open 状态，"
                       "学生在 end_time 之前刷脸签到。")
        intro.setStyleSheet("color: gray; padding: 8px;")
        layout.addWidget(intro)

        self.create_btn = QPushButton("＋ 发起新考勤")
        self.create_btn.setFixedHeight(40)
        self.create_btn.clicked.connect(self._on_create_task)
        layout.addWidget(self.create_btn)

        # 当前 open 的任务提示
        self.open_task_label = QLabel("当前没有进行中的考勤任务")
        self.open_task_label.setStyleSheet("padding: 8px; background: #f0f8ff;")
        layout.addWidget(self.open_task_label)
        self._refresh_open_task_label()

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _refresh_open_task_label(self):
        with session_scope() as s:
            dao = AttendanceTaskDao(s)
            open_tasks = [t for t in dao.find_by_teacher(self.user.id) if t.status == "open"]
        if not open_tasks:
            self.open_task_label.setText("当前没有进行中的考勤任务")
            self.open_task_label.setStyleSheet("padding: 8px; background: #f0f8ff;")
        else:
            t = open_tasks[0]
            self.open_task_label.setText(
                f"⏰ 任务 #{t.id} 进行中：{t.start_time:%Y-%m-%d %H:%M} ~ {t.end_time:%H:%M}"
            )
            self.open_task_label.setStyleSheet("padding: 8px; background: #fff8dc;")

    def _on_create_task(self):
        from src.ui.widgets.create_task_dialog import CreateTaskDialog
        dlg = CreateTaskDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_open_task_label()
            self._refresh_history()
            QMessageBox.information(self, "成功", "考勤任务已创建！")

    # =====================================================
    # Tab 2: 历史考勤
    # =====================================================
    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        toolbar = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._refresh_history)
        self.view_detail_btn = QPushButton("查看签到详情")
        self.view_detail_btn.clicked.connect(self._on_view_detail)
        self.close_task_btn = QPushButton("结束选中任务")
        self.close_task_btn.clicked.connect(self._on_close_task)
        self.pending_leave_btn = QPushButton("📝 待审批请假")
        self.pending_leave_btn.clicked.connect(self._on_review_leave)
        toolbar.addWidget(self.refresh_btn)
        toolbar.addWidget(self.view_detail_btn)
        toolbar.addWidget(self.pending_leave_btn)
        toolbar.addWidget(self.close_task_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["任务ID", "课程", "教室", "开始时间", "结束时间", "状态"]
        )
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.history_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.history_table)

        page.setLayout(layout)
        return page

    def _refresh_history(self):
        with session_scope() as s:
            tdao = AttendanceTaskDao(s)
            cdao = CourseDao(s)
            rdao = ClassroomDao(s)
            tasks = tdao.find_by_teacher(self.user.id)
            courses = {c.id: c for c in cdao.find_all()}
            rooms = {r.id: r for r in rdao.find_all()}

        self.history_table.setRowCount(len(tasks))
        for i, t in enumerate(tasks):
            c_obj = courses.get(t.course_id)
            r_obj = rooms.get(t.classroom_id)
            cname = c_obj.course_name if c_obj is not None else f"#{t.course_id}"
            rname = r_obj.name if r_obj is not None else f"#{t.classroom_id}"
            self.history_table.setItem(i, 0, QTableWidgetItem(str(t.id)))
            self.history_table.setItem(i, 1, QTableWidgetItem(cname))
            self.history_table.setItem(i, 2, QTableWidgetItem(rname))
            self.history_table.setItem(i, 3, QTableWidgetItem(t.start_time.strftime("%Y-%m-%d %H:%M")))
            self.history_table.setItem(i, 4, QTableWidgetItem(t.end_time.strftime("%Y-%m-%d %H:%M")))
            status_text = {"open": "🟢 进行中", "closed": "⚫ 已结束"}.get(t.status, t.status)
            self.history_table.setItem(i, 5, QTableWidgetItem(status_text))

    def _selected_task_id(self) -> int | None:
        row = self.history_table.currentRow()
        if row < 0:
            return None
        item = self.history_table.item(row, 0)
        return int(item.text()) if item else None

    def _on_view_detail(self):
        tid = self._selected_task_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个任务")
            return
        from src.ui.widgets.task_detail_dialog import TaskDetailDialog
        dlg = TaskDetailDialog(tid, parent=self)
        dlg.exec_()

    def _on_close_task(self):
        tid = self._selected_task_id()
        if tid is None:
            QMessageBox.information(self, "提示", "请先选中一个任务")
            return
        ret = QMessageBox.question(
            self, "确认", f"确定要结束任务 #{tid} 吗？\n结束后将自动标记缺勤学生。",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.attendance.close_task_and_mark_absent(tid)
            QMessageBox.information(self, "完成", "任务已结束，缺勤学生已标记")
            self._refresh_history()
            self._refresh_open_task_label()

    def _on_review_leave(self):
        """打开待审批请假弹窗 (W6 Phase 1)。"""
        from src.ui.widgets.leave_review_dialog import LeaveReviewDialog
        dlg = LeaveReviewDialog(self.user, parent=self)
        dlg.exec_()

    # =====================================================
    # Tab 3: 统计报表（占位）
    # =====================================================
    def _build_report_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        info = QLabel("📊 统计报表\n\nW4 接入 matplotlib 实现：\n"
                      "• 课程出勤率排行\n• 缺勤预警名单\n• 班级出勤趋势")
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: gray; font-size: 14px; padding: 40px;")
        layout.addWidget(info)
        page.setLayout(layout)
        return page

    # =====================================================
    # Tab 4: 账号
    # =====================================================
    def _build_account_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)

        info_box = QGroupBox("账号信息")
        form = QFormLayout()
        form.addRow("用户名:", QLabel(self.user.username))
        form.addRow("真实姓名:", QLabel(self.user.real_name))
        form.addRow("角色:", QLabel("教师"))
        form.addRow("邮箱:", QLabel(self.user.email or "—"))
        form.addRow("电话:", QLabel(self.user.phone or "—"))
        form.addRow("注册时间:", QLabel(self.user.created_at.strftime("%Y-%m-%d %H:%M") if self.user.created_at else "—"))
        info_box.setLayout(form)
        layout.addWidget(info_box)

        pwd_box = QGroupBox("修改密码")
        pwd_form = QFormLayout()
        self.old_pwd_edit = QLineEdit()
        self.old_pwd_edit.setEchoMode(QLineEdit.Password)
        self.new_pwd_edit = QLineEdit()
        self.new_pwd_edit.setEchoMode(QLineEdit.Password)
        self.new_pwd2_edit = QLineEdit()
        self.new_pwd2_edit.setEchoMode(QLineEdit.Password)
        pwd_form.addRow("原密码:", self.old_pwd_edit)
        pwd_form.addRow("新密码:", self.new_pwd_edit)
        pwd_form.addRow("确认新密码:", self.new_pwd2_edit)
        pwd_box.setLayout(pwd_form)
        layout.addWidget(pwd_box)

        change_btn = QPushButton("提交修改")
        change_btn.clicked.connect(self._on_change_password)
        layout.addWidget(change_btn)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def _on_change_password(self):
        old = self.old_pwd_edit.text()
        new = self.new_pwd_edit.text()
        new2 = self.new_pwd2_edit.text()
        if not (old and new and new2):
            QMessageBox.warning(self, "提示", "请填写完整")
            return
        if new != new2:
            QMessageBox.warning(self, "提示", "两次新密码不一致")
            return
        try:
            AuthService().change_password(self.user.id, old, new)
            QMessageBox.information(self, "成功", "密码已修改")
            self.old_pwd_edit.clear()
            self.new_pwd_edit.clear()
            self.new_pwd2_edit.clear()
        except AuthError as e:
            QMessageBox.warning(self, "失败", str(e))

    # =====================================================
    # 退出登录 / 关闭窗口
    # =====================================================
    def closeEvent(self, event):
        """用户点 X 关窗时调用, 关闭可能打开的弹窗避免悬挂引用."""
        # 关闭可能打开的请假审批弹窗 (W6 Phase 1 加的)
        for attr in ("leave_review_win", "task_detail_win", "new_pwd_win"):
            win = getattr(self, attr, None)
            if win is not None and hasattr(win, "close"):
                win.close()
        super().closeEvent(event)

    def _on_logout(self):
        ret = QMessageBox.question(self, "确认", "确定要退出登录吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            from src.ui.login_window import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()
