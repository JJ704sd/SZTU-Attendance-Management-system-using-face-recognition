"""
ui/student_window.py — 学生端主窗口

Phase 5 重写：3 个真实 Tab + 1 个 W4 占位。

- Tab 1 人脸注册：CameraWidget + 人脸框 + 弹 FaceCollectDialog
- Tab 2 刷脸签到：open 任务下拉 + 500ms QTimer 抓帧 + recognize
                 + sign_in_by_face；状态实时显示
- Tab 3 我的考勤：QTableWidget 查本人记录，状态着色
- Tab 4 我的实验室：占位 W4 接入

⚠️ 跨线程安全（CLAUDE.md 警告）：
- recognize() 走 _FaceCache.get() 单例，调用方在主线程，安全。
- CameraWidget._lock 是 bool 不是 threading.Lock；为避免 race，
  signin 不在子线程跑，500ms 主线程 tick 调 capture_one_frame
  + recognize（dlib 编码 ~50-100ms 不会完全卡 UI，且只 2 fps）。
"""
import logging
from typing import Optional

import numpy as np
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTabWidget,
    QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView, QAbstractItemView,
    QComboBox, QDialog,
)

from src.config import Config
from src.db import session_scope
from src.services.attendance_service import AttendanceService
from src.services.face_service import FaceService, recognize
from src.utils.face_helper import face_encodings, face_locations
from src.models.user import User
from src.ui.styles import welcome_suffix
from src.ui.widgets.camera_widget import CameraWidget

log = logging.getLogger(__name__)

# 状态 → (颜色, 文本)
STATUS_DISPLAY = {
    "present": ("#16A34A", "✅ 出勤"),
    "late":    ("#D97706", "⚠️ 迟到"),
    "absent":  ("#DC2626", "❌ 缺勤"),
    "leave":   ("#2563EB", "📝 请假"),
}


class StudentWindow(QWidget):
    def __init__(self, user: User):
        super().__init__()
        self.user = user
        self.face_service = FaceService()
        self.attendance_service = AttendanceService()

        # Tab 2 签到状态
        self._current_task_id: Optional[int] = None
        self._signing_in = False
        self._signin_timer = QTimer(self)
        self._signin_timer.setInterval(500)  # 2 fps
        self._signin_timer.timeout.connect(self._on_signin_tick)

        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"学生端 — {self.user.real_name}")
        self.resize(900, 640)

        # 顶部信息条（与教师端一致风格）
        top = QHBoxLayout()
        welcome = QLabel(f"欢迎，{self.user.real_name}{welcome_suffix(self.user)}")
        wf = QFont(); wf.setPointSize(12); wf.setBold(True)
        welcome.setFont(wf)
        top.addWidget(welcome)
        top.addStretch()
        info = QLabel(f"用户名: {self.user.username} | 学号: {self.user.student_id or '—'}")
        info.setStyleSheet("color: gray;")
        top.addWidget(info)
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        # Tab
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_register_tab(), "人脸注册")
        self.tabs.addTab(self._build_signin_tab(),   "刷脸签到")
        self.tabs.addTab(self._build_my_attendance_tab(), "我的考勤")
        self.tabs.addTab(self._build_leave_tab(),    "我的请假")
        # Tab 切换时刷新对应数据
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 主布局
        main = QVBoxLayout()
        main.addLayout(top)
        main.addWidget(self.tabs)
        self.setLayout(main)

    # ==================================================================
    # Tab 1: 人脸注册
    # ==================================================================
    def _build_register_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        intro = QLabel(
            f"需采集 {Config.FACE_SAMPLE_COUNT} 张不同角度的人脸。\n"
            f"注册后即可在「刷脸签到」Tab 进行考勤。"
        )
        intro.setStyleSheet("color: gray; padding: 6px;")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.register_status = QLabel("加载中...")
        self.register_status.setProperty("role", "status")
        layout.addWidget(self.register_status)

        # 摄像头预览
        self.register_camera = CameraWidget()
        self.register_camera.setMinimumSize(480, 360)
        self.register_camera.set_overlay_callback(self._draw_face_boxes)
        layout.addWidget(self.register_camera)

        # 按钮
        btn_row = QHBoxLayout()
        self.open_reg_cam_btn = QPushButton("打开摄像头")
        self.open_reg_cam_btn.clicked.connect(lambda: self._open_camera(self.register_camera, self.open_reg_cam_btn))
        self.collect_btn = QPushButton("开始采集")
        self.collect_btn.setProperty("role", "primary")
        self.collect_btn.clicked.connect(self._on_start_collect)
        btn_row.addWidget(self.open_reg_cam_btn)
        btn_row.addWidget(self.collect_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        page.setLayout(layout)
        self._refresh_register_status()
        return page

    def _refresh_register_status(self):
        n = len(self.face_service.load_user_encodings(self.user.id))
        if n == 0:
            self._set_label_state(self.register_status,
                                  "当前未注册人脸 — 请点击「开始采集」", "neutral")
        elif n < Config.FACE_SAMPLE_COUNT:
            self._set_label_state(self.register_status,
                                  f"已注册 {n} 张（建议 ≥ {Config.FACE_SAMPLE_COUNT} 张以提高识别率）", "neutral")
        else:
            self._set_label_state(self.register_status,
                                  f"已注册 {n} 张 ✓ 可去「刷脸签到」", "success")

    def _on_start_collect(self):
        if not self.register_camera.is_running():
            QMessageBox.warning(self, "提示", "请先打开摄像头")
            return
        from src.ui.widgets.face_collect_dialog import FaceCollectDialog
        dlg = FaceCollectDialog(self.user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "成功",
                                    f"注册成功！本次采集 {dlg.saved_count} 张")
            self._refresh_register_status()

    # ==================================================================
    # Tab 2: 刷脸签到
    # ==================================================================
    def _build_signin_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        # 任务下拉
        task_row = QHBoxLayout()
        task_row.addWidget(QLabel("考勤任务:"))
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(300)
        task_row.addWidget(self.task_combo)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_open_tasks)
        task_row.addWidget(refresh_btn)
        task_row.addStretch()
        layout.addLayout(task_row)

        # 摄像头
        self.signin_camera = CameraWidget()
        self.signin_camera.setMinimumSize(480, 360)
        self.signin_camera.set_overlay_callback(self._draw_face_boxes)
        layout.addWidget(self.signin_camera)

        # 状态
        self.signin_status = QLabel("就绪 — 选择任务后点击「开始签到」")
        self.signin_status.setProperty("role", "status")
        self.signin_status.setWordWrap(True)
        layout.addWidget(self.signin_status)

        # 按钮
        btn_row = QHBoxLayout()
        self.open_signin_cam_btn = QPushButton("打开摄像头")
        self.open_signin_cam_btn.clicked.connect(
            lambda: self._open_camera(self.signin_camera, self.open_signin_cam_btn))
        self.start_signin_btn = QPushButton("开始签到")
        self.start_signin_btn.setProperty("role", "primary")
        self.start_signin_btn.clicked.connect(self._on_start_signin)
        self.stop_signin_btn = QPushButton("停止")
        self.stop_signin_btn.clicked.connect(self._on_stop_signin)
        self.stop_signin_btn.setEnabled(False)
        btn_row.addWidget(self.open_signin_cam_btn)
        btn_row.addWidget(self.start_signin_btn)
        btn_row.addWidget(self.stop_signin_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()
        page.setLayout(layout)
        self._refresh_open_tasks()
        return page

    def _refresh_open_tasks(self):
        from src.dao.attendance_dao import AttendanceTaskDao
        with session_scope() as s:
            tasks = AttendanceTaskDao(s).find_open_tasks()

        self.task_combo.clear()
        if not tasks:
            self.task_combo.addItem("（暂无 open 任务）", None)
            self.start_signin_btn.setEnabled(False)
            return
        self.start_signin_btn.setEnabled(True)
        for t in tasks:
            label = f"任务 #{t.id} - {t.start_time:%m-%d %H:%M} ~ {t.end_time:%H:%M}"
            self.task_combo.addItem(label, t.id)

    def _on_start_signin(self):
        task_id = self.task_combo.currentData()
        if not task_id:
            QMessageBox.warning(self, "提示", "没有可签到的任务")
            return
        if not self.signin_camera.is_running():
            QMessageBox.warning(self, "提示", "请先打开摄像头")
            return
        self._current_task_id = task_id
        self._signing_in = True
        self._signin_timer.start()
        self._set_label_state(self.signin_status,
                              f"签到中...请正对摄像头（任务 #{task_id}）", "neutral")
        self.start_signin_btn.setEnabled(False)
        self.stop_signin_btn.setEnabled(True)

    def _on_stop_signin(self):
        self._signing_in = False
        self._signin_timer.stop()
        self._set_label_state(self.signin_status, "已停止", "neutral")
        self.start_signin_btn.setEnabled(True)
        self.stop_signin_btn.setEnabled(False)

    def _on_signin_tick(self):
        """500ms 一次：抓帧 → face_encodings → recognize → 命中就签到。"""
        if not self._signing_in or not self.signin_camera.is_running():
            return
        frame = self.signin_camera.capture_one_frame()
        if frame is None:
            return
        try:
            locs = face_locations(frame)
        except Exception:
            log.exception("face_locations 异常")
            return
        if not locs:
            return
        try:
            encs = face_encodings(frame, known_face_locations=locs)
        except Exception:
            log.exception("face_encodings 异常")
            return
        if not encs:
            return
        try:
            result = recognize(encs[0])
        except Exception:
            log.exception("recognize 异常")
            return
        if result is None:
            return
        user_id, distance = result
        if user_id != self.user.id:
            # 别人脸：继续识别，不签到
            self._set_label_state(self.signin_status,
                                  f"识别到他人（user_id={user_id}，距离={distance:.3f}），继续...", "neutral")
            return
        # 是我 → 签到
        self._on_stop_signin()
        try:
            record = self.attendance_service.sign_in_by_face(
                self._current_task_id, self.user.id, distance)
        except Exception as e:
            QMessageBox.critical(self, "异常", f"签到异常：{e}")
            return
        if record is None:
            QMessageBox.information(self, "提示",
                                    "签到失败（可能任务已关闭或已签到）")
            return
        self._set_label_state(self.signin_status,
                              f"签到成功！{record.sign_in_time:%H:%M:%S} - 状态: {record.status}",
                              "success")
        QMessageBox.information(self, "成功",
                                f"签到成功！\n状态: {record.status}\n距离: {distance:.4f}")
        # 任务可能因签到而从 open 列表移除 → 刷新下拉
        self._refresh_open_tasks()

    # ==================================================================
    # Tab 3: 我的考勤
    # ==================================================================
    def _build_my_attendance_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()

        toolbar = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_my_attendance)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self.attendance_table = QTableWidget()
        self.attendance_table.setColumnCount(5)
        self.attendance_table.setHorizontalHeaderLabels(
            ["签到时间", "任务ID", "状态", "匹配距离", "备注"]
        )
        self.attendance_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.attendance_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.attendance_table)

        page.setLayout(layout)
        return page

    def _refresh_my_attendance(self):
        from src.dao.attendance_dao import AttendanceRecordDao
        with session_scope() as s:
            records = AttendanceRecordDao(s).find_by_student(self.user.id)

        self.attendance_table.setRowCount(len(records))
        for i, r in enumerate(records):
            sign_in = r.sign_in_time
            self.attendance_table.setItem(
                i, 0,
                QTableWidgetItem(sign_in.strftime("%Y-%m-%d %H:%M:%S") if sign_in else "—"))
            self.attendance_table.setItem(i, 1, QTableWidgetItem(f"#{r.task_id}"))

            color_hex, status_text = STATUS_DISPLAY.get(r.status, ("#6B7280", r.status))
            status_item = QTableWidgetItem(status_text)
            status_item.setForeground(QColor(color_hex))
            self.attendance_table.setItem(i, 2, status_item)

            self.attendance_table.setItem(
                i, 3,
                QTableWidgetItem(f"{r.match_score:.4f}" if r.match_score is not None else "—"))
            self.attendance_table.setItem(
                i, 4,
                QTableWidgetItem("缺勤/补录" if r.sign_in_time is None else ""))

    # ==================================================================
    # Tab 4: 我的请假（W6 Phase 1 接入 LeaveService）
    # ==================================================================
    def _build_leave_tab(self) -> QWidget:
        """请假申请 + 历史查询。"""
        page = QWidget()
        layout = QVBoxLayout()

        info = QLabel("📝 请假申请\n\n对 open 状态的考勤任务发起请假, 老师审批后自动计入考勤记录")
        info.setStyleSheet("color: gray;")
        layout.addWidget(info)

        # 工具栏
        toolbar = QHBoxLayout()
        self.apply_leave_btn = QPushButton("📝 申请请假")
        self.apply_leave_btn.setProperty("role", "primary")
        self.apply_leave_btn.clicked.connect(self._on_apply_leave)
        self.refresh_leave_btn = QPushButton("🔄 刷新")
        self.refresh_leave_btn.clicked.connect(self._refresh_my_leaves)
        toolbar.addWidget(self.apply_leave_btn)
        toolbar.addWidget(self.refresh_leave_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 请假历史表
        self.leave_table = QTableWidget()
        self.leave_table.setColumnCount(5)
        self.leave_table.setHorizontalHeaderLabels(
            ["申请时间", "任务ID", "原因", "状态", "审批备注"]
        )
        self.leave_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.leave_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.leave_table)

        page.setLayout(layout)
        return page

    def _refresh_my_leaves(self):
        """刷新本人请假历史。"""
        from src.services.leave_service import LeaveService
        leaves = LeaveService().list_by_student(self.user.id)
        self.leave_table.setRowCount(len(leaves))
        for i, r in enumerate(leaves):
            self.leave_table.setItem(
                i, 0,
                QTableWidgetItem(r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "—"))
            self.leave_table.setItem(i, 1, QTableWidgetItem(f"#{r.task_id}"))
            self.leave_table.setItem(i, 2, QTableWidgetItem(r.reason or ""))
            color, text = {
                "pending": ("#D97706", "⏳ 待审批"),
                "approved": ("#16A34A", "✅ 已批准"),
                "rejected": ("#DC2626", "❌ 已拒绝"),
            }.get(r.status, ("#6B7280", r.status))
            status_item = QTableWidgetItem(text)
            status_item.setForeground(QColor(color))
            self.leave_table.setItem(i, 3, status_item)
            self.leave_table.setItem(i, 4, QTableWidgetItem(
                f"审批人 #{r.approver_id} @ {r.approve_time:%m-%d %H:%M}" if r.approver_id else ""
            ))

    def _on_apply_leave(self):
        """申请请假：弹输入框选 task_id + reason。"""
        from src.dao.attendance_dao import AttendanceTaskDao
        from src.services.leave_service import LeaveError, LeaveService

        # 1. 列出 open 任务给选
        with session_scope() as s:
            open_tasks = AttendanceTaskDao(s).find_open_tasks()
        if not open_tasks:
            QMessageBox.information(self, "提示", "没有 open 任务可以请假")
            return
        # 简化: 直接输入 task_id (任务多时改成 combo)
        from PyQt5.QtWidgets import QInputDialog
        task_items = [f"#{t.id} - {t.start_time:%m-%d %H:%M}" for t in open_tasks]
        task_label, ok = QInputDialog.getItem(
            self, "选任务", "请选择要请假的任务:", task_items, 0, False,
        )
        if not ok:
            return
        # 从 label 解析出 task_id (W11: 加 try/except 防 label 格式变更崩溃)
        try:
            task_id = int(task_label.split(" - ")[0].lstrip("#"))
        except (ValueError, IndexError):
            QMessageBox.warning(self, "提示", f"无法解析任务: {task_label}")
            return
        # 输入 reason
        reason, ok = QInputDialog.getText(
            self, "请假原因", "请输入请假原因 (10 字以上):",
        )
        if not ok or not reason.strip() or len(reason.strip()) < 5:
            QMessageBox.warning(self, "提示", "请输入至少 5 个字的请假原因")
            return
        # 提交
        try:
            req = LeaveService().student_apply(self.user.id, task_id, reason.strip())
            QMessageBox.information(self, "成功", f"请假申请已提交 (id=#{req.id})")
            self._refresh_my_leaves()
        except LeaveError as e:
            QMessageBox.warning(self, "申请失败", str(e))

    # ==================================================================
    # 公共辅助
    # ==================================================================
    def _draw_face_boxes(self, bgr: np.ndarray) -> np.ndarray:
        """CameraWidget overlay 回调：画绿色人脸框。"""
        try:
            import cv2
            locs = face_locations(bgr)
            for (top, right, bottom, left) in locs:
                cv2.rectangle(bgr, (left, top), (right, bottom), (0, 255, 0), 2)
        except Exception:
            log.exception("画人脸框异常")
        return bgr

    def _open_camera(self, camera: CameraWidget, btn: QPushButton):
        # W8 修复: 避免两个 CameraWidget 同时打开 device_id=0 冲突
        # (cv2.VideoCapture 同一 device 只能一个 handle, 后开的前面就废了)
        if camera is self.register_camera and self.signin_camera.is_running():
            self.signin_camera.stop()
        elif camera is self.signin_camera and self.register_camera.is_running():
            self.register_camera.stop()
        if camera.start(0):
            btn.setText("关闭摄像头")
            try:
                btn.clicked.disconnect()
            except TypeError:
                pass
            btn.clicked.connect(lambda: self._close_camera(camera, btn))
        else:
            QMessageBox.warning(self, "提示", "摄像头打开失败")

    def _close_camera(self, camera: CameraWidget, btn: QPushButton):
        camera.stop()
        btn.setText("打开摄像头")
        try:
            btn.clicked.disconnect()
        except TypeError:
            pass
        btn.clicked.connect(lambda: self._open_camera(camera, btn))

    def _set_label_state(self, label: QLabel, text: str, state: str):
        label.setText(text)
        label.setProperty("state", state)
        label.style().unpolish(label)
        label.style().polish(label)

    def _on_tab_changed(self, idx: int):
        # 切到 Tab 0（注册）刷新状态
        if idx == 0:
            self._refresh_register_status()
        # 切到 Tab 1（签到）刷新任务
        elif idx == 1:
            self._refresh_open_tasks()
        # 切到 Tab 2（我的考勤）刷新表格
        elif idx == 2:
            self._refresh_my_attendance()
        # 切到 Tab 3（请假）刷新表格
        elif idx == 3:
            self._refresh_my_leaves()

    # ==================================================================
    # 退出登录 / 关闭窗口
    # ==================================================================
    def _cleanup_resources(self):
        """释放摄像头 + 签到 timer (closeEvent + _on_logout 都会调)."""
        if self._signing_in:
            self._on_stop_signin()
        if self.register_camera.is_running():
            self.register_camera.stop()
        if self.signin_camera.is_running():
            self.signin_camera.stop()

    def closeEvent(self, event):
        """用户点 X 关窗时自动调用, 避免摄像头/timer 资源泄漏."""
        self._cleanup_resources()
        super().closeEvent(event)

    def _on_logout(self):
        ret = QMessageBox.question(self, "确认", "确定要退出登录吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            self._cleanup_resources()
            # 回登录窗
            from src.ui.login_window import LoginWindow
            self.login_win = LoginWindow()
            self.login_win.show()
            self.close()
