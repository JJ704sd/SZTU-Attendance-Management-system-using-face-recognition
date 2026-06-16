"""
ui/widgets/training_admin_tab.py — 实验室管理员 Tab 2「安全培训录入」

W4 Phase 5b: LabTraining 记录的 CRUD UI
复用 Phase 5a LabAdminTab 模式（工具栏 + 弹窗 + 表格 + 状态标签）
字段不同: student_id + lab_id + training_type + completion/expiry_date + score + instructor_id
"""
import logging
from datetime import date
from typing import Optional

from PyQt5.QtCore import QDate, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QHBoxLayout, QHeaderView, QLabel,
    QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget,
)

from src.dao.lab_dao import LabDao
from src.dao.lab_training_dao import LabTrainingDao
from src.dao.user_dao import UserDao
from src.db import session_scope
from src.models.lab import LabTraining
from src.models.user import User

log = logging.getLogger(__name__)

TRAINING_TYPES = ["生物", "化学", "辐射", "设备"]


class TrainingEditDialog(QDialog):
    """增/改培训记录的弹窗表单。"""

    def __init__(self, training: Optional[LabTraining] = None, parent=None):
        super().__init__(parent)
        self.training = training
        self.setWindowTitle("编辑培训记录" if training else "新增培训记录")
        # W14+ 演示模式: 窗口 +80x60
        self.resize(520, 420)
        self._init_ui()
        if training:
            self._load_from(training)

    def _init_ui(self):
        layout = QVBoxLayout()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        # 加载 student / lab / teacher 选项（在 with session_scope() 内查）
        with session_scope() as s:
            students = UserDao(s).find_by_role("student")
            labs = LabDao(s).find_all()
            teachers = UserDao(s).find_by_role("teacher")
            admins = UserDao(s).find_by_role("lab_admin")
            instructors = teachers + admins

        # student 必填
        self.student_combo = QComboBox()
        for u in students:
            self.student_combo.addItem(
                f"#{u.id} {u.real_name} ({u.student_id or u.username})", u.id,
            )
        form.addRow("学生*:", self.student_combo)

        # lab 必填
        self.lab_combo = QComboBox()
        for lab in labs:
            self.lab_combo.addItem(
                f"#{lab.id} {lab.name} (L{lab.safety_level})", lab.id,
            )
        form.addRow("实验室*:", self.lab_combo)

        # 培训类型必填
        self.training_combo = QComboBox()
        self.training_combo.addItems(TRAINING_TYPES)
        form.addRow("培训类型*:", self.training_combo)

        # 完成日期 + 到期日期
        today = QDate.currentDate()
        self.completion_edit = QDateEdit(today.addDays(-10))
        self.completion_edit.setCalendarPopup(True)
        self.completion_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("完成日期*:", self.completion_edit)

        self.expiry_edit = QDateEdit(today.addDays(355))  # 默认 1 年后
        self.expiry_edit.setCalendarPopup(True)
        self.expiry_edit.setDisplayFormat("yyyy-MM-dd")
        form.addRow("到期日期*:", self.expiry_edit)

        # 分数
        self.score_spin = QDoubleSpinBox()
        self.score_spin.setRange(0.0, 100.0)
        self.score_spin.setValue(85.0)
        self.score_spin.setSingleStep(0.5)
        form.addRow("分数*:", self.score_spin)

        # 培训教师（可选）
        self.instructor_combo = QComboBox()
        self.instructor_combo.addItem("（未指派）", None)
        for u in instructors:
            self.instructor_combo.addItem(
                f"#{u.id} {u.real_name} ({u.role})", u.id,
            )
        form.addRow("培训教师:", self.instructor_combo)

        layout.addLayout(form)

        # 按钮
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("保存")
        btns.button(QDialogButtonBox.Cancel).setText("取消")
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        self.setLayout(layout)

    def _load_from(self, t: LabTraining):
        # student
        for i in range(self.student_combo.count()):
            if self.student_combo.itemData(i) == t.student_id:
                self.student_combo.setCurrentIndex(i)
                break
        # lab
        for i in range(self.lab_combo.count()):
            if self.lab_combo.itemData(i) == t.lab_id:
                self.lab_combo.setCurrentIndex(i)
                break
        # training type
        if t.training_type in TRAINING_TYPES:
            self.training_combo.setCurrentText(t.training_type)
        # dates
        if t.completion_date:
            self.completion_edit.setDate(QDate(
                t.completion_date.year, t.completion_date.month, t.completion_date.day,
            ))
        if t.expiry_date:
            self.expiry_edit.setDate(QDate(
                t.expiry_date.year, t.expiry_date.month, t.expiry_date.day,
            ))
        # score
        if t.score is not None:
            self.score_spin.setValue(t.score)
        # instructor
        if t.instructor_id is not None:
            for i in range(self.instructor_combo.count()):
                if self.instructor_combo.itemData(i) == t.instructor_id:
                    self.instructor_combo.setCurrentIndex(i)
                    break

    def _on_accept(self):
        # 校验：到期日期必须 > 完成日期
        if self.expiry_edit.date() <= self.completion_edit.date():
            QMessageBox.warning(self, "提示", "到期日期必须晚于完成日期")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "student_id": self.student_combo.currentData(),
            "lab_id": self.lab_combo.currentData(),
            "training_type": self.training_combo.currentText(),
            "completion_date": self.completion_edit.date().toPyDate(),
            "expiry_date": self.expiry_edit.date().toPyDate(),
            "score": self.score_spin.value(),
            "instructor_id": self.instructor_combo.currentData(),
        }


class TrainingAdminTab(QWidget):
    """Tab 2 安全培训录入。"""

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
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["ID", "学生", "实验室", "培训类型", "完成日期", "到期日期", "分数"]
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

    def refresh(self):
        with session_scope() as s:
            trainings = LabTrainingDao(s).find_all()
            # 查学生姓名映射
            student_ids = {t.student_id for t in trainings}
            lab_ids = {t.lab_id for t in trainings}
            students = {u.id: u for u in UserDao(s).find_by_role("student")}
            labs = {l.id: l for l in LabDao(s).find_all()}

        self.table.setRowCount(len(trainings))
        today = date.today()
        for i, t in enumerate(trainings):
            stu = students.get(t.student_id)
            lab = labs.get(t.lab_id)
            # 到期日期着色：过期红、临期（30 天内）橙
            if t.expiry_date < today:
                color = "#DC2626"  # 红
            elif (t.expiry_date - today).days <= 30:
                color = "#D97706"  # 橙
            else:
                color = "#1F2937"  # 普通文字色

            self.table.setItem(i, 0, QTableWidgetItem(str(t.id)))
            self.table.setItem(i, 1, QTableWidgetItem(
                f"#{stu.id} {stu.real_name}" if stu else f"#{t.student_id}"
            ))
            self.table.setItem(i, 2, QTableWidgetItem(
                f"#{lab.id} {lab.name}" if lab else f"#{t.lab_id}"
            ))
            self.table.setItem(i, 3, QTableWidgetItem(t.training_type or "—"))
            self.table.setItem(i, 4, QTableWidgetItem(
                t.completion_date.isoformat() if t.completion_date else "—"
            ))
            expiry_item = QTableWidgetItem(
                t.expiry_date.isoformat() if t.expiry_date else "—"
            )
            expiry_item.setForeground(QColor_for_color(color))
            self.table.setItem(i, 5, expiry_item)
            self.table.setItem(i, 6, QTableWidgetItem(
                f"{t.score:.1f}" if t.score is not None else "—"
            ))
        self._set_status(f"已加载 {len(trainings)} 条培训记录")

    def _on_add(self):
        dlg = TrainingEditDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                with session_scope() as s:
                    LabTrainingDao(s).add(LabTraining(**data))
                self._set_status(f"已新增培训记录", "success")
            except Exception as e:
                log.exception("新增培训记录失败")
                QMessageBox.critical(self, "失败", f"新增失败：{e}")
            self.refresh()

    def _on_edit(self):
        record = self._get_selected_record()
        if record is None:
            return
        dlg = TrainingEditDialog(training=record, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            try:
                with session_scope() as s:
                    target = s.get(LabTraining, record.id)
                    if target is None:
                        QMessageBox.warning(self, "提示", "该记录已被删除")
                        return
                    for k, v in data.items():
                        setattr(target, k, v)
                self._set_status(f"已更新培训记录 #{record.id}", "success")
            except Exception as e:
                log.exception("更新培训记录失败")
                QMessageBox.critical(self, "失败", f"更新失败：{e}")
            self.refresh()

    def _on_delete(self):
        record = self._get_selected_record()
        if record is None:
            return
        ret = QMessageBox.question(
            self, "确认",
            f"确定删除培训记录 #{record.id} 吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret != QMessageBox.Yes:
            return
        try:
            with session_scope() as s:
                target = s.get(LabTraining, record.id)
                if target is None:
                    QMessageBox.warning(self, "提示", "该记录已被删除")
                    return
                LabTrainingDao(s).delete(target)
            self._set_status(f"已删除培训记录 #{record.id}", "success")
        except Exception as e:
            log.exception("删除培训记录失败")
            QMessageBox.critical(self, "失败", f"删除失败：{e}")
        self.refresh()

    def _get_selected_record(self) -> Optional[LabTraining]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请先选中一条记录")
            return None
        id_item = self.table.item(row, 0)
        if id_item is None:
            return None
        try:
            record_id = int(id_item.text())
        except ValueError:
            return None
        with session_scope() as s:
            return s.get(LabTraining, record_id)

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


# Helper: QColor 实例化（QColor_for_color 名字为了避命名空间混淆）
def QColor_for_color(color_hex: str):
    from PyQt5.QtGui import QColor
    return QColor(color_hex)
