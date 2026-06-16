"""
ui/student_window.py — 学生端主窗口

W2-W12 历程：
- Tab 1 人脸注册：CameraWidget + 人脸框 + 弹 FaceCollectDialog
- Tab 2 刷脸签到：open 任务下拉 + 500ms QTimer 抓帧 + recognize
                 + sign_in_by_face；状态实时显示
- Tab 3 我的考勤：QTableWidget 查本人记录，状态着色
- Tab 4 我的请假：leave_request 学生申请 + 历史查询

W13+ 改造（track-b-student-ui）：
- Tab 2 改成分段控件 (QTabWidget 子 Tab)：
    - 子 Tab 0 「🤳 刷脸签到」   → 沿用原 _on_signin_tick / sign_in_by_face 链路
    - 子 Tab 1 「🔢 数字码签到」 → DigitSigninWidget
    - 子 Tab 2 「📷 二维码签到」 → QrScanWidget
- 任务下拉保持在外层，三个子 Tab 共享同一 task_id.
- 三种签到方式「先到先签」：监听 DigitSigninWidget.signin_succeeded /
  QrScanWidget.signin_succeeded / 刷脸成功 → 在外层 disable 整个子 QTabWidget
  并顶部提示「你已签到 (xxx 方式)」.
- 换任务时三个子 Tab 都要重新初始化（reset_for_new_task）.

⚠️ 跨线程安全（CLAUDE.md 警告）：
- recognize() 走 _FaceCache.get() 单例，调用方在主线程，安全。
- CameraWidget._lock 是 bool 不是 threading.Lock；为避免 race，
  signin 不在子线程跑，500ms 主线程 tick 调 capture_one_frame
  + recognize（dlib 编码 ~50-100ms 不会完全卡 UI，且只 2 fps）。
"""
import logging
import shutil
from typing import Optional

import numpy as np
from PyQt5.QtCore import Qt, QTimer
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
from src.ui.widgets.digit_signin_widget import DigitSigninWidget
from src.ui.widgets.qr_scan_widget import QrScanWidget

log = logging.getLogger(__name__)

# W14 现代化: 表格行高/表头高度 —— 与 styles.py 间距尺度保持一致
TABLE_ROW_HEIGHT = 32       # 单元格高度 (px), 适合 14px 字号 + 8px 上下内边距
TABLE_HEADER_HEIGHT = 38    # 表头高度 (px), GLOBAL_QSS 已有 10px 上下 padding

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

        # W13+: 提前创建刷脸 CameraWidget (原 W12 是在 _build_signin_tab 里 new 的,
        # 现在拆到子 Tab 里, 但 _open_camera / _cleanup_resources / _on_start_signin
        # 都需要引用 self.signin_camera —— 必须在构造时 new, 避免 AttributeError).
        self.signin_camera = CameraWidget()
        # 任务下拉占位引用 —— 真实控件在 _build_signin_tab 里 new 后赋值.
        self.task_combo: Optional[QComboBox] = None

        # Tab 2 签到状态
        self._current_task_id: Optional[int] = None
        self._signing_in = False
        self._signin_timer = QTimer(self)
        self._signin_timer.setInterval(500)  # 2 fps
        self._signin_timer.timeout.connect(self._on_signin_tick)
        # W13+: 三种签到方式「先到先签」追踪（None / 'face' / 'digit' / 'qr'）
        # 签到成功后置位, 父窗口 disable 整个 signin_subtabs 并顶部提示.
        self._signed_in_method: Optional[str] = None
        # 内部锁: _on_sub_signin_succeeded 调 _refresh_open_tasks 时置位, 防止
        # _on_task_changed 误把 banner / subtabs 灰显状态清掉.
        self._signed_in_lock: bool = False
        # W14: 刷脸提示去重 —— 500ms tick 反复触发陌生人脸/他人脸时,
        # 只在文案变化时刷新状态栏, 让 warning 视觉态保持可见
        # (不清掉之前的提示, 让用户能稳定看到 "请对准摄像头本人" 之类).
        self._last_face_status: Optional[str] = None

        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(f"学生端 — {self.user.real_name}")
        # W14 现代化: 窗口高度 +40, 容纳 4 个 Tab + 顶部条更宽松
        self.resize(960, 680)

        # 顶部信息条（与教师端一致风格）
        # W14: top spacing 加大, 让 welcome 标题与右侧 info 间距更舒展
        top = QHBoxLayout()
        top.setSpacing(16)
        welcome = QLabel(f"欢迎，{self.user.real_name}{welcome_suffix(self.user)}")
        wf = QFont(); wf.setPointSize(12); wf.setBold(True)
        welcome.setFont(wf)
        top.addWidget(welcome)
        top.addStretch()
        info = QLabel(f"用户名: {self.user.username} | 学号: {self.user.student_id or '—'}")
        info.setStyleSheet("color: gray;")
        top.addWidget(info)
        # W12: 色彩状态标签 (不可点, 替代之前的 3 模式按钮).
        # 3 模式实现统一走 cv2.cvtColor, 切换没视觉差异, 砍掉按钮避免误导.
        self.color_mode_label = QLabel("🎨 颜色 OK")
        self.color_mode_label.setStyleSheet(
            "color: #16A34A; padding: 4px 10px; "
            "background-color: #DCFCE7; border-radius: 4px;"
        )
        self.color_mode_label.setToolTip(
            "摄像头色彩已统一走 cv2.cvtColor(BGR→RGB) 显式转换,\n"
            "不依赖 PyQt5 内部行为, 显示颜色正确."
        )
        top.addWidget(self.color_mode_label)
        self.logout_btn = QPushButton("退出登录")
        self.logout_btn.clicked.connect(self._on_logout)
        top.addWidget(self.logout_btn)

        # Tab
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_register_tab(), "人脸注册")
        self.tabs.addTab(self._build_signin_tab(),   "签到（刷脸/数字码/二维码）")
        self.tabs.addTab(self._build_my_attendance_tab(), "我的考勤")
        self.tabs.addTab(self._build_leave_tab(),    "我的请假")
        # Tab 切换时刷新对应数据
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # 主布局
        # W14: 主布局 margin/spacing 加大
        main = QVBoxLayout()
        main.setContentsMargins(12, 12, 12, 12)
        main.setSpacing(10)
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
        # W14 现代化: 状态 banner 加 padding + 卡片底色 (与登录/注册一致)
        self.register_status.setStyleSheet(
            "QLabel {"
            " background-color: #FFFFFF;"
            " border: 1px solid #E5E7EB;"
            " border-radius: 8px;"
            " padding: 10px 14px;"
            "}"
        )
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
        # W12 v6: 学生端能自己管理人脸数据, 不必找管理员
        self.clear_my_face_btn = QPushButton("🗑 清空我的人脸")
        self.clear_my_face_btn.setProperty("role", "danger")
        self.clear_my_face_btn.setToolTip(
            "删除你所有已注册的人脸数据 (face_encoding + jpg 图片).\n"
            "删除后需要重新采集才能签到. 不删账号."
        )
        self.clear_my_face_btn.clicked.connect(self._on_clear_my_face)
        btn_row.addWidget(self.open_reg_cam_btn)
        btn_row.addWidget(self.collect_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.clear_my_face_btn)
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
            # W12 v5: 30 张是"单轮目标" (保证单次多样性), 不是"总上限".
            # 多次采 30+19=49 张是正常的, 多角度多场景更鲁棒.
            self._set_label_state(self.register_status,
                                  f"已注册 {n} 张（本轮 30 张目标，还没采满）— 多次采集可累加，识别率更高", "neutral")
        else:
            self._set_label_state(self.register_status,
                                  f"已注册 {n} 张 ✓ 多角度多次采更准，可去「刷脸签到」", "success")

    def _on_start_collect(self):
        if not self.register_camera.is_running():
            QMessageBox.warning(self, "提示", "请先打开摄像头")
            return
        from src.ui.widgets.face_collect_dialog import FaceCollectDialog
        # W12 修复: 传 register_camera 给 dialog 复用, 避免双开 device 0 冲突
        dlg = FaceCollectDialog(self.user, camera_widget=self.register_camera, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            QMessageBox.information(self, "成功",
                                    f"注册成功！本次采集 {dlg.saved_count} 张")
            self._refresh_register_status()

    def _on_clear_my_face(self):
        """W12 v6: 学生端清空自己的人脸数据 (face_encoding + jpg + 缓存).

        不删账号, 只删人脸数据. 跟管理员 Tab 5 用同套逻辑, 但限定 self.user.id.
        """
        from PyQt5.QtCore import Qt
        n_enc = len(self.face_service.load_user_encodings(self.user.id))
        if n_enc == 0:
            QMessageBox.information(
                self, "提示",
                "你当前没有注册人脸数据, 无需清空。",
            )
            return
        ret = QMessageBox.question(
            self, "⚠️ 请确认",
            f"确定要清空 <b>你自己</b> 的 <b>{n_enc}</b> 条人脸数据吗？\n\n"
            f"会同时:\n"
            f"  1. 删 face_encoding 表的 {n_enc} 条记录\n"
            f"  2. 删 dataset/face_images/{self.user.id}/ 下的所有 jpg\n"
            f"  3. 清 _FaceCache 中你的缓存\n\n"
            f"账号不会被删除。清空后你需要重新采集才能签到。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # 默认 No 防误点
        )
        if ret != QMessageBox.Yes:
            return

        # 跟管理员 Tab 5 一样的删除流程, 但用 busy cursor + disable 按钮
        from PyQt5.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.clear_my_face_btn.setEnabled(False)
        try:
            n_db = self.face_service.delete_user_encodings(self.user.id)
            # 删 jpg 目录
            user_dir = Config.DATASET_DIR / str(self.user.id)
            n_files = 0
            if user_dir.exists():
                n_files = sum(1 for _ in user_dir.glob("*.jpg"))
                shutil.rmtree(user_dir, ignore_errors=True)
            # 清缓存 (只清自己)
            from src.services.face_service import _FaceCache
            _FaceCache.get().remove_user(self.user.id)
            QMessageBox.information(
                self, "成功",
                f"已清空 {n_db} 条人脸编码 + {n_files} 个 jpg 文件。\n"
                f"你现在可以重新采集。",
            )
        except Exception as e:
            log.exception("清空人脸数据失败")
            QMessageBox.critical(self, "失败", f"清空失败：{e}")
        finally:
            QApplication.restoreOverrideCursor()
            self.clear_my_face_btn.setEnabled(True)
        self._refresh_register_status()

    # ==================================================================
    # Tab 2: 签到（刷脸 / 数字码 / 二维码 三种方式）
    # ==================================================================
    def _build_signin_tab(self) -> QWidget:
        """W13+ 改造: Tab 2 内部再嵌一个 QTabWidget (子 Tab 0/1/2 = 刷脸/数字码/二维码).

        任务下拉 + 刷新按钮放外层, 三个子 Tab 共享同一 task_id.
        三个子 Tab 互相独立, 通过监听 signin_succeeded 信号做「先到先签」灰显.
        """
        page = QWidget()
        # W14: 签到 Tab 整体间距加大
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(14, 14, 14, 14)

        # ===== 顶部: 任务下拉 + 「你已签到」提示 =====
        # W14: top_row 间距加大, 让任务下拉区与 banner 不挤
        top_row = QVBoxLayout()
        top_row.setSpacing(10)
        task_row = QHBoxLayout()
        task_row.setSpacing(10)
        task_row.addWidget(QLabel("考勤任务:"))
        self.task_combo = QComboBox()
        self.task_combo.setMinimumWidth(300)
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        task_row.addWidget(self.task_combo)
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self._refresh_open_tasks)
        task_row.addWidget(refresh_btn)
        task_row.addStretch()
        top_row.addLayout(task_row)

        # 「你已签到」横幅（默认隐藏）
        self.signed_in_banner = QLabel("")
        self.signed_in_banner.setProperty("role", "status")
        self.signed_in_banner.setProperty("state", "success")
        self.signed_in_banner.setStyleSheet(
            "color: white; background-color: #16A34A; "
            "padding: 8px 14px; border-radius: 6px; font-weight: bold; font-size: 13px;"
        )
        self.signed_in_banner.setVisible(False)
        top_row.addWidget(self.signed_in_banner)
        layout.addLayout(top_row)

        # ===== 中部: 子 QTabWidget (刷脸 / 数字码 / 二维码) =====
        # 三个子 Tab widget 延迟构造: 等用户选 task 后再创建 (依赖 task_id).
        self.signin_subtabs = QTabWidget()
        # 三个 placeholder 页面 —— 在 _refresh_open_tasks 里首次构造后会替换.
        self._face_tab_idx = -1
        self._digit_tab_idx = -1
        self._qr_tab_idx = -1
        self._face_tab: Optional[QWidget] = None
        self._digit_widget: Optional[DigitSigninWidget] = None
        self._qr_widget: Optional[QrScanWidget] = None
        # 先放 3 个占位 page (QLabel), 等 _refresh_open_tasks 真正拿到 task_id 后再 rebuild.
        placeholder = QLabel("请先在上方选择任务")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: gray; padding: 60px;")
        for i, name in enumerate(["🤳 刷脸签到", "🔢 数字码签到", "📷 二维码签到"]):
            self.signin_subtabs.addTab(placeholder, name)
        layout.addWidget(self.signin_subtabs)

        layout.addStretch()
        page.setLayout(layout)
        self._refresh_open_tasks()
        return page

    def _on_task_changed(self, _idx: int):
        """任务下拉变化 → 重建/重置三个子 Tab widget, 取消「已签到」标记.

        W13+: _signed_in_lock 用于防御 _refresh_open_tasks 在签到成功后被调时,
        误重置 banner + 重新 enable subtabs. 设置了 lock 就只同步 _current_task_id
        + rebuild, 不动 banner / 灰显状态.
        """
        task_id = self.task_combo.currentData()
        if task_id == self._current_task_id:
            return
        self._current_task_id = task_id
        # 切换任务 = 新一轮签到, 清掉「先到先签」状态
        # (除非在 signed_in_lock 期间 —— 此时是 _refresh_open_tasks 内部触发, 不重置)
        if not getattr(self, "_signed_in_lock", False):
            self._signed_in_method = None
            self.signed_in_banner.setVisible(False)
            self.signin_subtabs.setEnabled(True)
        if task_id is None:
            return
        # 重建三个子 Tab 内容 (首次) 或 reset 现有 (换任务)
        self._rebuild_signin_subtabs(task_id)

    def _rebuild_signin_subtabs(self, task_id: int):
        """按 task_id 重新初始化三个子 Tab widget.

        首次调用: 三个子 Tab 是占位 QLabel, 替换成真实 widget.
        后续调用: 子 Tab 已存在, 调 reset_for_new_task() 即可 (保留 camera/timer 状态).
        """
        if self._face_tab is None:
            # 首次: 构造刷脸 Tab 内容（CameraWidget + 控制按钮）
            self._face_tab = self._build_face_signin_page(task_id)
            self._digit_widget = DigitSigninWidget(
                self, task_id, self.user.id, self.attendance_service)
            self._qr_widget = QrScanWidget(
                self, task_id, self.user.id, self.attendance_service)

            # 替换占位 page —— 从后往前 remove 避免 index 偏移
            # (3 个 placeholder 共用同一 QLabel 实例, addTab 重复引用同一个 widget)
            while self.signin_subtabs.count() > 0:
                self.signin_subtabs.removeTab(self.signin_subtabs.count() - 1)
            # 按顺序插入真实 widget
            self._face_tab_idx = self.signin_subtabs.addTab(self._face_tab, "🤳 刷脸签到")
            self._digit_tab_idx = self.signin_subtabs.addTab(self._digit_widget, "🔢 数字码签到")
            self._qr_tab_idx = self.signin_subtabs.addTab(self._qr_widget, "📷 二维码签到")

            # 连 signin_succeeded 信号到父窗口, 统一处理「先到先签」灰显
            self._digit_widget.signin_succeeded.connect(self._on_sub_signin_succeeded)
            self._qr_widget.signin_succeeded.connect(self._on_sub_signin_succeeded)
        else:
            # 后续换任务: reset 三个子 Tab
            if self._digit_widget is not None:
                self._digit_widget.reset_for_new_task(task_id)
            if self._qr_widget is not None:
                self._qr_widget.reset_for_new_task(task_id)
            # 刷脸 Tab 内 task_id 来自 task_combo 重新读, 不需要 reset_for_new_task
            # (它每次 _on_signin_tick 都读 self._current_task_id, 实时跟随)

    def _build_face_signin_page(self, task_id: int) -> QWidget:
        """刷脸签到子 Tab 的页面构造.

        把原 _build_signin_tab 里的刷脸 UI 整段搬过来, 引用外层 self.signin_camera /
        self.open_signin_cam_btn / self.start_signin_btn / self.stop_signin_btn /
        self.signin_status, 这些属性保持在 StudentWindow 上, 避免改动 _on_signin_tick
        / _on_start_signin / _on_stop_signin / _open_camera / _close_camera.
        """
        page = QWidget()
        layout = QVBoxLayout()

        # 摄像头 (已在 __init__ 创建 self.signin_camera, 这里直接 add 进来 + 配 overlay)
        self.signin_camera.setMinimumSize(480, 360)
        self.signin_camera.set_overlay_callback(self._draw_face_boxes)
        layout.addWidget(self.signin_camera)

        # 状态
        self.signin_status = QLabel("就绪 — 选择任务后点击「开始签到」")
        self.signin_status.setProperty("role", "status")
        self.signin_status.setWordWrap(True)
        # W14 现代化: 状态 banner 加大 padding, warning 视觉态更明显
        self.signin_status.setStyleSheet(
            "QLabel {"
            " background-color: #FFFFFF;"
            " border: 1px solid #E5E7EB;"
            " border-radius: 8px;"
            " padding: 12px 16px;"
            " font-size: 13px;"
            "}"
        )
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
        # 提示当前 task_id
        self.signin_status.setText(f"就绪 — 当前任务 #{task_id}，点击「开始签到」")
        return page

    def _on_sub_signin_succeeded(self, record):
        """DigitSigninWidget / QrScanWidget 发 signin_succeeded 时调用.

        父窗口统一处理: 顶部 banner + disable 子 QTabWidget, 避免重复签到.
        """
        if self._signed_in_method is not None:
            # 已经签过 (刷脸成功后又收到数字码/二维码 signal) —— 防御
            return
        method_label = {
            "face": "刷脸", "digit": "数字码", "qr": "二维码",
        }.get(record.signin_method, record.signin_method)
        self._signed_in_method = record.signin_method
        self.signed_in_banner.setText(
            f"✅ 你已签到（{method_label}方式）— {record.sign_in_time:%H:%M:%S}，状态: {record.status}"
        )
        self.signed_in_banner.setVisible(True)
        # 停掉所有可能的后台活动
        if self._signing_in:
            self._on_stop_signin()
        # 灰显整个子 QTabWidget —— 三种方式都不可再签
        self.signin_subtabs.setEnabled(False)
        # 任务可能因签到而从 open 列表移除 → 刷新下拉.
        # 用 _signed_in_lock 防止 _on_task_changed 误把 banner / subtabs 状态重置.
        self._signed_in_lock = True
        try:
            self._refresh_open_tasks()
        finally:
            self._signed_in_lock = False
        # _refresh_open_tasks 末尾调了 _on_task_changed, 可能把 subtabs enable 了,
        # 重新 disable + 把 banner 显示回来.
        self.signin_subtabs.setEnabled(False)
        self.signed_in_banner.setVisible(True)


    def _refresh_open_tasks(self):
        from src.dao.attendance_dao import AttendanceTaskDao
        with session_scope() as s:
            tasks = AttendanceTaskDao(s).find_open_tasks()

        # W13+: 刷新前先 block 信号, 避免 clear() 触发 currentIndexChanged(None)
        # 把 subtabs 弄成「无任务」空状态, 然后 addItem() 又触发一次 change.
        # 这里靠 _on_task_changed 内部比较 current vs _current_task_id 已经去重,
        # 但 block 更干净.
        self.task_combo.blockSignals(True)
        try:
            self.task_combo.clear()
            if not tasks:
                self.task_combo.addItem("（暂无 open 任务）", None)
            else:
                for t in tasks:
                    label = f"任务 #{t.id} - {t.start_time:%m-%d %H:%M} ~ {t.end_time:%H:%M}"
                    self.task_combo.addItem(label, t.id)
        finally:
            self.task_combo.blockSignals(False)

        # start_signin_btn / open_signin_cam_btn 在 _build_face_signin_page 之前不存在
        if not hasattr(self, "start_signin_btn"):
            return
        if not tasks:
            self.start_signin_btn.setEnabled(False)
        else:
            self.start_signin_btn.setEnabled(True)

        # 显式触发一次 _on_task_changed, 让 subtabs 根据当前选项初始化
        # (addItem 第一项 = 第一个 task, currentIndex=0, _on_task_changed 会拿到 task_id)
        self._on_task_changed(self.task_combo.currentIndex())

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
        # W14: 重置刷脸提示去重状态, 新一轮签到开始时把上一轮的 warning 清掉
        self._last_face_status = None
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
        """500ms 一次：抓帧 → face_encodings → recognize → 命中就签到。

        W14 改造:
        - 陌生人脸 (recognize 返回 None): 静默改为 warning 提示
          "未识别到人脸，请对准摄像头本人"
        - 识别到他人 (user_id != self.user.id): 中性提示改为 warning
          "检测到其他用户，非本人签到无效。请本人面对摄像头",
          不再泄露内部 user_id
        - 用 self._last_face_status 去重: 同一文案不重复 setText/polish,
          让 warning 状态稳定可见, 不被下一帧覆盖消失
        """
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
            # W14: 陌生人脸 → warning 提示用户调整位置/本人面对摄像头
            self._update_face_status("未识别到人脸，请对准摄像头本人", "warning")
            return
        user_id, distance = result
        if user_id != self.user.id:
            # W14: 识别到他人 → warning 提示, 不暴露内部 user_id
            self._update_face_status(
                "检测到其他用户，非本人签到无效。请本人面对摄像头", "warning")
            return
        # 是我 → 签到
        # 重置去重状态, 让 _on_sub_signin_succeeded / _set_label_state(success) 正常生效
        self._last_face_status = None
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
        # W13+: 走统一的「先到先签」灰显流程 (banner + disable subtabs + 刷新任务下拉)
        self._on_sub_signin_succeeded(record)

    def _update_face_status(self, text: str, state: str):
        """W14: 刷脸提示去重 —— 同一文案不重复调用 setProperty/polish,
        让 warning 视觉态在 500ms tick 间稳定可见, 不被下一帧覆盖闪一下就消失.

        调用方: _on_signin_tick 的陌生人脸 / 识别到他人分支.
        """
        if self._last_face_status == text:
            return  # 文案没变, 不重复刷 QSS
        self._last_face_status = text
        self._set_label_state(self.signin_status, text, state)

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
        # W14 现代化: 斑马纹 + 行高/表头高度加大
        self.attendance_table.setAlternatingRowColors(True)
        self.attendance_table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self.attendance_table.verticalHeader().setVisible(False)
        self.attendance_table.horizontalHeader().setFixedHeight(TABLE_HEADER_HEIGHT)
        self.attendance_table.setSelectionBehavior(QAbstractItemView.SelectRows)
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
        # W14 现代化: 斑马纹 + 行高/表头高度加大
        self.leave_table.setAlternatingRowColors(True)
        self.leave_table.verticalHeader().setDefaultSectionSize(TABLE_ROW_HEIGHT)
        self.leave_table.verticalHeader().setVisible(False)
        self.leave_table.horizontalHeader().setFixedHeight(TABLE_HEADER_HEIGHT)
        self.leave_table.setSelectionBehavior(QAbstractItemView.SelectRows)
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
        """释放摄像头 + 签到 timer (closeEvent + _on_logout 都会调).

        W13+: 三个子 Tab 都要清理——
            - 刷脸: self.signin_camera (共用 CameraWidget)
            - 数字码: 无 timer/camera
            - 二维码: self._qr_widget.camera + scan timer (子 widget 的 closeEvent 会兜底,
              这里额外显式调一次防御)
        """
        if self._signing_in:
            self._on_stop_signin()
        if hasattr(self, "register_camera") and self.register_camera.is_running():
            self.register_camera.stop()
        if hasattr(self, "signin_camera") and self.signin_camera.is_running():
            self.signin_camera.stop()
        # W13+: 二维码子 Tab 的 timer + 独立 camera
        if self._qr_widget is not None:
            try:
                # 子 widget 自己的 closeEvent 已经在父 close 链里被调, 但显式再 stop 一次
                # 保证 timer 一定停 (防御 Qt delete 顺序问题).
                self._qr_widget._stop_scan_internal()
                if self._qr_widget.camera.is_running():
                    self._qr_widget.camera.stop()
            except Exception:
                log.exception("cleanup _qr_widget 异常")

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
