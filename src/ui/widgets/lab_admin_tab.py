"""
ui/widgets/lab_admin_tab.py — 实验室管理员 Tab 1「实验室管理」

W4 Phase 5a: 实验室的 CRUD UI
- QTableWidget 列表（不可编辑）
- 工具栏: 新增 / 编辑 / 删除 / 刷新
- LabEditDialog 弹窗表单: 名称/位置/安全等级/培训类型/管理员
"""
import logging
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.dao.lab_dao import LabDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.course import Laboratory
from src.models.user import User

log = logging.getLogger(__name__)

# 培训类型选项（跟 LabTraining.training_type 保持一致）
TRAINING_TYPES = ["生物", "化学", "辐射", "设备"]


class LabEditDialog(QDialog):
    """增/改实验室的弹窗表单。"""

    def __init__(self, lab: Optional[Laboratory] = None, parent=None):
        super().__init__(parent)
        self.lab = lab
        self.setWindowTitle("编辑实验室" if lab else "新增实验室")
        # W14+ 演示模式: 窗口 +60x60
        self.resize(480, 340)
        self._init_ui()
        if lab:
            self._load_from(lab)

    def _init_ui(self):
        layout = QVBoxLayout()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例：BME-1 嵌入式实验室")
        form.addRow("名称*:", self.name_edit)

        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("例：C栋301")
        form.addRow("位置:", self.location_edit)

        self.safety_spin = QSpinBox()
        self.safety_spin.setRange(1, 5)
        self.safety_spin.setValue(2)
        form.addRow("安全等级*:", self.safety_spin)

        self.training_combo = QComboBox()
        self.training_combo.addItems(TRAINING_TYPES)
        form.addRow("要求的培训:", self.training_combo)

        # 管理员: 选 user（可选，None=未指派）
        self.manager_combo = QComboBox()
        self.manager_combo.addItem("（未指派）", None)
        with session_scope() as s:
            admins = UserDao(s).find_by_role("lab_admin")
            teachers = UserDao(s).find_by_role("teacher")
        for u in admins + teachers:
            label = f"#{u.id} {u.real_name} ({u.role})"
            self.manager_combo.addItem(label, u.id)
        form.addRow("管理员:", self.manager_combo)

        layout.addLayout(form)

        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("保存")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def _load_from(self, lab: Laboratory):
        """从已有 lab 加载到表单。"""
        self.name_edit.setText(lab.name or "")
        self.location_edit.setText(lab.location or "")
        self.safety_spin.setValue(lab.safety_level or 2)
        if lab.required_training and lab.required_training in TRAINING_TYPES:
            self.training_combo.setCurrentText(lab.required_training)
        if lab.manager_id is not None:
            for i in range(self.manager_combo.count()):
                if self.manager_combo.itemData(i) == lab.manager_id:
                    self.manager_combo.setCurrentIndex(i)
                    break

    def _on_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "提示", "名称不能为空")
            return
        self.accept()

    def get_data(self) -> dict:
        """返回表单数据（不写 DB，由调用方处理）。"""
        return {
            "name": self.name_edit.text().strip(),
            "location": self.location_edit.text().strip() or None,
            "safety_level": self.safety_spin.value(),
            "required_training": self.training_combo.currentText(),
            "manager_id": self.manager_combo.currentData(),
        }


class LabAdminTab(QWidget):
    """Tab 1 实验室管理。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()
        self.add_btn = QPushButton("＋ 新增")
        self.add_btn.setProperty("role", "primary")
        self.add_btn.clicked.connect(self._on_add)
        self.edit_btn = QPushButton("✎ 编辑")
        self.edit_btn.clicked.connect(self._on_edit)
        self.del_btn = QPushButton("🗑 删除")
        self.del_btn.setProperty("role", "danger")
        self.del_btn.clicked.connect(self._on_delete)
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.add_btn)
        toolbar.addWidget(self.edit_btn)
        toolbar.addWidget(self.del_btn)
        toolbar.addStretch()
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "名称", "位置", "安全等级", "要求培训", "管理员"]
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

    # ----- 工具栏回调 -----
    def refresh(self):
        with session_scope() as s:
            labs = LabDao(s).find_all()
        self.table.setRowCount(len(labs))
        for i, lab in enumerate(labs):
            # 查 manager 名
            manager_label = "（未指派）"
            if lab.manager_id is not None:
                with session_scope() as s:
                    u = UserDao(s).get(lab.manager_id)
                    if u:
                        manager_label = f"#{u.id} {u.real_name}"
            self.table.setItem(i, 0, QTableWidgetItem(str(lab.id)))
            self.table.setItem(i, 1, QTableWidgetItem(lab.name or ""))
            self.table.setItem(i, 2, QTableWidgetItem(lab.location or "—"))
            self.table.setItem(i, 3, QTableWidgetItem(str(lab.safety_level)))
            self.table.setItem(i, 4, QTableWidgetItem(lab.required_training or "—"))
            self.table.setItem(i, 5, QTableWidgetItem(manager_label))
        self._set_status(f"已加载 {len(labs)} 个实验室")

    def _on_add(self):
        dlg = LabEditDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                with session_scope() as s:
                    LabDao(s).add(Laboratory(**data))
                self._set_status(f"已新增实验室: {data['name']}", "success")
            except Exception as e:
                log.exception("新增实验室失败")
                QMessageBox.critical(self, "失败", f"新增失败：{e}")
            self.refresh()

    def _on_edit(self):
        lab = self._get_selected_lab()
        if lab is None:
            return
        dlg = LabEditDialog(lab=lab, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                with session_scope() as s:
                    target = LabDao(s).find_by_id(lab.id)
                    if target is None:
                        QMessageBox.warning(self, "提示", "该实验室已被删除")
                        return
                    for k, v in data.items():
                        setattr(target, k, v)
                self._set_status(f"已更新实验室 #{lab.id}", "success")
            except Exception as e:
                log.exception("更新实验室失败")
                QMessageBox.critical(self, "失败", f"更新失败：{e}")
            self.refresh()

    def _on_delete(self):
        lab = self._get_selected_lab()
        if lab is None:
            return
        ret = QMessageBox.question(
            self, "确认",
            f"确定删除实验室 #{lab.id} '{lab.name}' 吗？\n"
            f"（同时会级联删除 lab_training / lab_access_log 中相关记录）",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        try:
            with session_scope() as s:
                target = LabDao(s).find_by_id(lab.id)
                if target is None:
                    QMessageBox.warning(self, "提示", "该实验室已被删除")
                    return
                LabDao(s).delete(target)
            self._set_status(f"已删除实验室 #{lab.id}", "success")
        except Exception as e:
            log.exception("删除实验室失败")
            QMessageBox.critical(self, "失败", f"删除失败：{e}")
        self.refresh()

    def _get_selected_lab(self) -> Optional[Laboratory]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一个实验室")
            return None
        id_item = self.table.item(row, 0)
        if id_item is None:
            return None
        try:
            lab_id = int(id_item.text())
        except ValueError:
            return None
        with session_scope() as s:
            return LabDao(s).find_by_id(lab_id)

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
