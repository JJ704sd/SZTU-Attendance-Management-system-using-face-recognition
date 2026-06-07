"""
ui/widgets/face_admin_tab.py — 实验室管理员 Tab 5「用户人脸管理」

W12: 让 lab_admin 能在 GUI 上:
- 看到所有用户 + 各自的 face_encoding 数量
- 删除某个用户的所有人脸数据 (face_encoding 行 + dataset/ 下 jpg 文件)
- 自动清 _FaceCache 让识别立刻生效

不删 user 行 (不删账号), 只删人脸数据.
"""
import logging
import shutil
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QMessageBox,
    QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.config import Config
from src.dao.face_dao import FaceEncodingDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.face import FaceEncoding
from src.models.user import User

log = logging.getLogger(__name__)


class FaceAdminTab(QWidget):
    """Tab 5 用户人脸管理 — 让管理员清掉某人的人脸数据.

    用法:
    - 列表显示所有用户 + 各自的 face_encoding 数量
    - 选中用户 → 点「🗑 删除该用户人脸」→ 二次确认 → 删 DB + 删 jpg + 刷缓存
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout()

        # 顶部说明
        intro = QLabel(
            "⚠️ 管理员可删除任意用户的人脸采集数据 (face_encoding + dataset/ 下 jpg)。\n"
            "删除后该用户需要重新采集才能刷脸签到。账号本身不会被删除。"
        )
        intro.setStyleSheet(
            "color: #92400E; background-color: #FEF3C7; "
            "padding: 10px 14px; border-radius: 6px;"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # 工具栏
        toolbar = QHBoxLayout()
        self.del_btn = QPushButton("🗑 删除该用户人脸")
        self.del_btn.setProperty("role", "danger")
        self.del_btn.clicked.connect(self._on_delete)
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.del_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "用户名", "真实姓名", "角色", "已注册编码数"]
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

    # -----------------------------------------------------
    # 数据加载
    # -----------------------------------------------------
    def refresh(self):
        """加载所有用户 + 各自 face_encoding 数量."""
        from collections import Counter
        with session_scope() as s:
            # UserDao 没 find_all, 用 s.query(User).all() 直接查
            users = s.query(User).order_by(User.id).all()
            # 一次查所有 encoding, group by user_id
            counter = Counter(uid for uid, in s.query(FaceEncoding.user_id).all())

        self.table.setRowCount(len(users))
        for i, u in enumerate(users):
            n = counter.get(u.id, 0)
            self.table.setItem(i, 0, QTableWidgetItem(str(u.id)))
            self.table.setItem(i, 1, QTableWidgetItem(u.username or ""))
            self.table.setItem(i, 2, QTableWidgetItem(u.real_name or ""))
            self.table.setItem(i, 3, QTableWidgetItem(u.role or ""))
            count_item = QTableWidgetItem(str(n))
            # 编码数 = 0 时灰显, > 0 时高亮
            if n == 0:
                count_item.setForeground(Qt.gray)
            else:
                count_item.setForeground(Qt.darkGreen)
            self.table.setItem(i, 4, count_item)

        total = sum(counter.values())
        self._set_status(
            f"已加载 {len(users)} 个用户, 总计 {total} 条人脸编码",
            "neutral",
        )

    # -----------------------------------------------------
    # 删除
    # -----------------------------------------------------
    def _get_selected_user(self) -> Optional[User]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一个用户")
            return None
        id_item = self.table.item(row, 0)
        if id_item is None:
            return None
        try:
            user_id = int(id_item.text())
        except ValueError:
            return None
        # W12 修复: UserDao 没 find_by_id, 用 s.get(User, user_id) 替代
        with session_scope() as s:
            return s.get(User, user_id)

    def _on_delete(self):
        user = self._get_selected_user()
        if user is None:
            return

        # 二次确认
        n_enc = self._count_encodings(user.id)
        if n_enc == 0:
            QMessageBox.information(
                self, "提示",
                f"用户 {user.username} ({user.real_name}) 当前没有注册人脸数据, 无需删除。",
            )
            return
        ret = QMessageBox.question(
            self, "⚠️ 危险操作 — 请确认",
            f"确定要删除用户 <b>{user.username}</b> ({user.real_name}) "
            f"的 <b>{n_enc}</b> 条人脸数据吗？\n\n"
            f"会同时:\n"
            f"  1. 删 face_encoding 表的 {n_enc} 条记录\n"
            f"  2. 删 dataset/face_images/{user.id}/ 下的所有 jpg\n"
            f"  3. 清 _FaceCache 中该用户的缓存\n\n"
            f"用户账号不会被删除。删除后该用户需重新采集才能签到。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # 默认 No 防误点
        )
        if ret != QMessageBox.Yes:
            self._set_status("已取消", "neutral")
            return

        # W12 修复: 删的过程 (DB + 文件 + cache) 全部在主线程但加 busy cursor + disable 按钮,
        # 避免用户以为卡了. 同时改用 remove_user(user_id) 替代 refresh() 全表重载,
        # 158 个用户时不卡死 GUI.
        from PyQt5.QtCore import Qt
        from PyQt5.QtWidgets import QApplication
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.del_btn.setEnabled(False)
        self._set_status("删除中...", "neutral")
        try:
            n_db = self._do_delete_db(user.id)
            n_files = self._do_delete_files(user.id)
            self._do_remove_user_from_cache(user.id)  # W12: 只删该用户, 不 refresh 全表
            self._set_status(
                f"✅ 已删除 {user.username} 的 {n_db} 条编码 + {n_files} 个 jpg 文件",
                "success",
            )
            QMessageBox.information(
                self, "成功",
                f"已删除 {n_db} 条人脸编码, {n_files} 个图片文件。\n"
                f"用户 {user.username} 现在可以重新采集。",
            )
        except Exception as e:
            log.exception("删除人脸数据失败")
            QMessageBox.critical(self, "失败", f"删除失败：{e}")
            self._set_status(f"❌ 删除失败: {e}", "error")
        finally:
            QApplication.restoreOverrideCursor()
            self.del_btn.setEnabled(True)
        self.refresh()

    def _count_encodings(self, user_id: int) -> int:
        with session_scope() as s:
            return len(FaceEncodingDao(s).find_by_user(user_id))

    def _do_delete_db(self, user_id: int) -> int:
        """删 face_encoding 行, 返回删除条数."""
        with session_scope() as s:
            return FaceEncodingDao(s).delete_by_user(user_id)

    def _do_delete_files(self, user_id: int) -> int:
        """删 dataset/face_images/{user_id}/ 下的所有 jpg (连空目录一起删)."""
        user_dir = Config.DATASET_DIR / str(user_id)
        if not user_dir.exists():
            return 0
        n = 0
        # 用 shutil.rmtree 直接删目录 (比手写 glob 简洁)
        try:
            # 先数文件 (因为 rmtree 删了之后没法数)
            n = sum(1 for _ in user_dir.glob("*.jpg"))
            shutil.rmtree(user_dir, ignore_errors=True)
        except Exception as e:
            log.warning("删 dataset 目录失败 (非致命): %s", e)
        return n

    def _do_remove_user_from_cache(self, user_id: int):
        """W12 修复: 从 _FaceCache 只弹掉该用户 (不 refresh 全表, 避免 GUI 卡).

        之前 _do_refresh_cache 调 _FaceCache.refresh() 会全表拉所有用户编码,
        158 个用户时主线程假死几秒 → 用户以为"卡退".
        remove_user(user_id) 只 pop 掉该用户, O(1).
        """
        try:
            from src.services.face_service import _FaceCache
            _FaceCache.get().remove_user(user_id)
            log.info("W12: _FaceCache 已 remove_user(%s)", user_id)
        except Exception as e:
            log.warning("W12: _FaceCache remove_user 失败 (非致命): %s", e)

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
