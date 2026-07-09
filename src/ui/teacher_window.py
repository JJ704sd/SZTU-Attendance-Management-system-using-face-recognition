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

# W14 现代化: 表格行高/表头高度 —— 与 student_window / admin_window 保持一致
TABLE_ROW_HEIGHT = 32
TABLE_HEADER_HEIGHT = 38


class TeacherWindow(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user  # 已登录的教师 User
        self.attendance = AttendanceService()
        # W15+: 当前签到码弹窗引用 (用于"重复点二维码签到"时复用 stop 老 web_server)
        self.signin_code_win = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"教师端 — {self.user.real_name}")
        # W14+ 演示模式: 窗口 +240x160 容纳更大字号和摄像头, 1080P 投影不挤
        self.resize(1200, 800)

        # 顶部
        # W14: top spacing 加大
        top = QHBoxLayout()
        top.setSpacing(16)
        welcome = QLabel(f"欢迎，{self.user.real_name}{welcome_suffix(self.user)}")
        welcome_font = QFont()
        # W14+ 演示模式: Welcome 字号 12→15, 投影清晰
        welcome_font.setPointSize(15)
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
        # W14: 主布局 margin/spacing 加大
        main = QVBoxLayout()
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)
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
        # W14: 签到 Tab 整体 margin/spacing 加大
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)
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
        # W14: 加 padding 加大 + 圆角, 与现代化卡片化对齐
        self.open_task_label = QLabel("当前没有进行中的考勤任务")
        self.open_task_label.setStyleSheet(
            "QLabel { padding: 12px 16px; border-radius: 8px; }"
        )
        layout.addWidget(self.open_task_label)
        self._refresh_open_task_label()

        # W13+: 签到码工具栏（对分易式「教师手动触发」）
        # 必须在有一个 open 任务时才能用，所以点按事件里再做"未选任务"提示
        signin_toolbar = QHBoxLayout()
        signin_toolbar.setSpacing(8)
        self.btn_digit_code = QPushButton("🎲 数字签到")
        self.btn_digit_code.setMinimumHeight(36)
        self.btn_digit_code.setToolTip("生成 4 位数字签到码，学生在 end_time 前输入此码签到")
        self.btn_digit_code.clicked.connect(lambda: self._on_open_signin_dialog("digit"))
        self.btn_qr_code = QPushButton("📱 二维码签到")
        self.btn_qr_code.setMinimumHeight(36)
        self.btn_qr_code.setToolTip("生成二维码签到码，学生扫码即可完成签到")
        self.btn_qr_code.clicked.connect(lambda: self._on_open_signin_dialog("qr"))
        signin_toolbar.addWidget(self.btn_digit_code)
        signin_toolbar.addWidget(self.btn_qr_code)
        signin_toolbar.addStretch()
        # 提示标签：告诉教师"对当前 open 任务生效"
        signin_hint = QLabel("对当前 open 任务生效（手动触发，码过期需点 🔄 刷新）")
        signin_hint.setStyleSheet("color: gray; font-size: 11px;")
        signin_toolbar.addWidget(signin_hint)
        layout.addLayout(signin_toolbar)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _refresh_open_task_label(self):
        with session_scope() as s:
            dao = AttendanceTaskDao(s)
            self._open_tasks = [t for t in dao.find_by_teacher(self.user.id) if t.status == "open"]
        if not self._open_tasks:
            self.open_task_label.setText("当前没有进行中的考勤任务")
            # W14: 中性卡片底色 (白 + 灰边 + 蓝文字)
            self.open_task_label.setStyleSheet(
                "QLabel { padding: 12px 16px; border-radius: 8px;"
                " background-color: #F8FAFC; color: #475569; border: 1px solid #E5E7EB; }"
            )
        else:
            t = self._open_tasks[0]
            self.open_task_label.setText(
                f"⏰ 任务 #{t.id} 进行中：{t.start_time:%Y-%m-%d %H:%M} ~ {t.end_time:%H:%M}"
            )
            # W14: 进行中卡片底色 (淡琥珀 + 琥珀边 + 琥珀字)
            self.open_task_label.setStyleSheet(
                "QLabel { padding: 12px 16px; border-radius: 8px;"
                " background-color: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }"
            )

    def _get_open_task_id(self) -> int | None:
        """返回当前教师第一个 open 任务的 id；没有则 None。

        W13+: 被数字签到 / 二维码签到按钮复用，避免重复查 DB。
        边界：若同时有多个 open 任务（极少见），只取最早创建的第一个；
        想要指定任务可在历史 Tab 选中行（_selected_task_id）。
        """
        if not getattr(self, "_open_tasks", None):
            return None
        return self._open_tasks[0].id

    def _on_create_task(self):
        from src.ui.widgets.create_task_dialog import CreateTaskDialog
        dlg = CreateTaskDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self._refresh_open_task_label()
            self._refresh_history()
            QMessageBox.information(self, "成功", "考勤任务已创建！")

    def _on_open_signin_dialog(self, code_type: str):
        """W13+: 教师点「数字签到 / 二维码签到」按钮 → 弹码显示弹窗。

        任务来源优先级:
          1) 当前 open 任务（_get_open_task_id）—— 教师最常用「边发边签」流程
          2) 退回到历史 Tab 选中行（_selected_task_id）—— 演示 / 重签场景
          3) 都没有 → 警告提示先创建/选中任务

        W14 增强（仅 code_type='qr'）:
          - 提前调 attendance.generate_signin_code 拿 token
          - 实例化并启动 SigninWebServer（FastAPI 嵌入）
          - 传 web_server 给 SigninCodeDialog，让 dialog 拿 url 做二维码内容
          - 若 web_server.start() 异常 → 弹 QMessageBox + 不创建 dialog（避免半启动状态）
        """
        task_id = self._get_open_task_id() or self._selected_task_id()
        if task_id is None:
            QMessageBox.warning(
                self, "无法生成签到码",
                "请先在「发起考勤」创建任务，或在「历史考勤」选中一个 open 任务",
            )
            return

        from src.ui.widgets.signin_code_dialog import SigninCodeDialog

        # W15+: 复用现有 dialog + web_server, 避免端口残留
        if self.signin_code_win is not None:
            try:
                old_win = self.signin_code_win
                old_web = getattr(old_win, "web_server", None)
                if old_web is not None:
                    try:
                        old_web.stop()
                        log.info("复用检查: stop 老的 SigninWebServer (port=%s)", old_web.port)
                    except Exception as e:
                        log.debug("stop 老 web_server 异常 (忽略): %s", e)
                old_win.close()
                old_win.deleteLater()
            except Exception as e:
                log.debug("关老 dialog 异常 (忽略): %s", e)
            finally:
                self.signin_code_win = None

        # W14: 仅 qr 类型启 web_server，digit 保持原行为（不启服务）
        web_server = None
        if code_type == "qr":
            try:
                # 1) 提前生成 token（dialog 内不再生成，避免重复 deactivate）
                result = self.attendance.generate_signin_code(task_id, "qr")
                if result is None:
                    QMessageBox.warning(
                        self, "生成失败",
                        "请确认任务状态为 open",
                    )
                    return
                token = result["code"]
                expires_at = result["expires_at"]

                # 2) 实例化 + 启动本地 HTTP 服务（端口冲突自动 +1）
                from src.services.signin_web import SigninWebServer
                web_server = SigninWebServer(
                    task_id=task_id,
                    token=token,
                    expires_at=expires_at,
                )
                web_server.start()
                log.info(
                    "W14 SigninWebServer 已启动: %s (task=%s)",
                    web_server.url, task_id,
                )
            except Exception as e:
                log.exception("启 SigninWebServer 失败: %s", e)
                QMessageBox.critical(
                    self, "启动本地签到服务失败",
                    f"无法启动二维码签到服务：\n{e}\n\n请检查端口占用或稍后重试。",
                )
                # 半启动状态清理: web_server 可能已部分启动
                if web_server is not None:
                    try:
                        web_server.stop()
                    except Exception:
                        pass
                return

        # 每次新建 widget —— 不缓存旧码（任务书边界要求）
        # 把引用挂在 self 上，closeEvent 时能主动关掉（防悬挂引用导致 timer 未停）
        self.signin_code_win = SigninCodeDialog(
            parent=self,
            task_id=task_id,
            code_type=code_type,
            teacher_window=self,
            web_server=web_server,
        )
        self.signin_code_win.exec_()

    # =====================================================
    # Tab 2: 历史考勤
    # =====================================================
    def _build_history_tab(self) -> QWidget:
        page = QWidget()
        # W14: 历史 Tab 整体 margin/spacing 加大
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # W14: toolbar 间距加大
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
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
        # W14 现代化: 斑马纹 + 行高/表头高度加大
        self.history_table.setAlternatingRowColors(True)
        self.history_table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.horizontalHeader().setFixedHeight(TABLE_HEADER_HEIGHT)
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
        if item is None:
            return None
        # W11: 加 try/except 防 item.text() 异常导致 UI 崩溃
        try:
            return int(item.text())
        except (ValueError, TypeError):
            return None

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
        """用户点 X 关窗时调用, 关闭可能打开的弹窗避免悬挂引用.

        R16 清理: 旧版 closeEvent 有 3 个 getattr 检查 (leave_review_win /
        task_detail_win / new_pwd_win), 但这 3 个属性从未在任何地方赋值:
        - LeaveReviewDialog / TaskDetailDialog 是 _on_review_leave /
          _on_view_detail 内的局部变量 (dlg.exec_()), 不挂 self
        - new_pwd_win 是误传, 修改密码就是 Account Tab 内的 QPushButton 触发
          (没有独立 dialog)
        → getattr 永远返 None, 是死代码. 删掉, 只保留真正挂在 self 上
        的 signin_code_win (数字码 / 二维码共用, 需主动关闭以释放端口).
        """
        # W13+: 关闭可能打开的签到码弹窗（数字码 / 二维码共用同一个 widget）
        #       其 closeEvent 会同步停 web_server + polling timer, 端口释放.
        win = getattr(self, "signin_code_win", None)
        if win is not None and hasattr(win, "close"):
            try:
                win.close()
            except Exception:
                log.exception("closeEvent 关闭 signin_code_win 异常 (忽略)")
        super().closeEvent(event)

    def _on_logout(self):
        ret = QMessageBox.question(self, "确认", "确定要退出登录吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            from src.ui.login_window import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()
