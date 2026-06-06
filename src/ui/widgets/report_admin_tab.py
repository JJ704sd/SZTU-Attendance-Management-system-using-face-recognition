"""
ui/widgets/report_admin_tab.py — 实验室管理员 Tab 4「使用率报表」

W4 Phase 5d: matplotlib 图表嵌入 PyQt5
- QComboBox 选 4 类图表
- FigureCanvasQTAgg 嵌入 Figure
- 工具栏根据图表类型动态显示过滤选项（实验室/课程/时间范围）
- 状态标签
"""
import logging
from typing import Optional

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from src.dao.lab_dao import LabDao
from src.db import session_scope
from src.services.report_service import ReportService
from src.utils.charts import (
    chart_absent_warning_table,
    chart_attendance_rate_bar,
    chart_attendance_trend_line,
    chart_lab_usage_heatmap,
)

log = logging.getLogger(__name__)

CHART_TYPES = [
    ("📊 出勤率排行（按课程）", "attendance_rate"),
    ("📈 出勤率趋势（按课程）", "attendance_trend"),
    ("🔥 实验室使用率热力图", "lab_usage"),
    ("⚠️ 缺勤预警名单", "absent_warning"),
]

DEFAULT_LAB_DAYS = 7
DEFAULT_ATTENDANCE_DAYS = 30


class ReportAdminTab(QWidget):
    """Tab 4 使用率报表。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvas: Optional[FigureCanvasQTAgg] = None
        self._init_ui()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout()

        # 工具栏
        toolbar = QHBoxLayout()

        self.chart_label = QLabel("图表:")
        toolbar.addWidget(self.chart_label)
        self.chart_combo = QComboBox()
        for label, value in CHART_TYPES:
            self.chart_combo.addItem(label, value)
        self.chart_combo.currentIndexChanged.connect(self._on_chart_type_changed)
        toolbar.addWidget(self.chart_combo)

        # 课程下拉（出勤率/趋势图用）
        self.course_label = QLabel("课程 ID:")
        toolbar.addWidget(self.course_label)
        self.course_edit = QComboBox()
        self.course_edit.setEditable(True)  # 让用户能输入任意 course_id
        self.course_edit.setMinimumWidth(120)
        toolbar.addWidget(self.course_edit)

        # 实验室下拉（热力图用）
        self.lab_label = QLabel("实验室:")
        toolbar.addWidget(self.lab_label)
        self.lab_combo = QComboBox()
        with session_scope() as s:
            labs = LabDao(s).find_all()
        self.lab_combo.addItem("（请选择）", None)
        for l in labs:
            self.lab_combo.addItem(f"#{l.id} {l.name}", l.id)
        toolbar.addWidget(self.lab_combo)

        # 缺勤阈值（缺勤预警用）
        self.threshold_label = QLabel("阈值:")
        toolbar.addWidget(self.threshold_label)
        self.threshold_combo = QComboBox()
        for pct in [60, 70, 80, 90]:
            self.threshold_combo.addItem(f"{pct}%", pct / 100)
        self.threshold_combo.setCurrentText("80%")
        toolbar.addWidget(self.threshold_combo)

        toolbar.addStretch()
        self.refresh_btn = QPushButton("🔄 刷新")
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_btn)
        layout.addLayout(toolbar)

        # 图表画布
        self.canvas_container = QWidget()
        self.canvas_layout = QVBoxLayout(self.canvas_container)
        self.canvas_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas_container, stretch=1)

        # 状态
        self.status_label = QLabel("就绪")
        self.status_label.setObjectName("status")
        self.status_label.setProperty("role", "status")
        layout.addWidget(self.status_label)
        self.setLayout(layout)

        # 默认隐藏 "课程 ID" 和 "实验室" 控件（按 chart_type 动态显示）
        self._on_chart_type_changed(0)

    def _on_chart_type_changed(self, _idx: int = 0):
        """根据图表类型显示/隐藏对应过滤选项。"""
        chart_type = self.chart_combo.currentData()

        # 课程相关：出勤率/趋势图用
        course_visible = chart_type in ("attendance_rate", "attendance_trend")
        self.course_label.setVisible(course_visible)
        self.course_edit.setVisible(course_visible)

        # 实验室相关：热力图用
        lab_visible = chart_type == "lab_usage"
        self.lab_label.setVisible(lab_visible)
        self.lab_combo.setVisible(lab_visible)

        # 阈值相关：缺勤预警用
        threshold_visible = chart_type == "absent_warning"
        self.threshold_label.setVisible(threshold_visible)
        self.threshold_combo.setVisible(threshold_visible)

        # 重新画
        self.refresh()

    def _clear_canvas(self):
        """切图表前清空旧 Figure（避免内存泄漏）。"""
        if self._canvas is not None:
            self.canvas_layout.removeWidget(self._canvas)
            self._canvas.setParent(None)
            self._canvas.deleteLater()
            self._canvas = None

    def _render(self, fig: Figure, success_msg: str):
        """把 matplotlib Figure 渲染到 Qt 画布。"""
        self._clear_canvas()
        self._canvas = FigureCanvasQTAgg(fig)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.canvas_layout.addWidget(self._canvas)
        self._canvas.draw()
        self._set_status(success_msg, "success")

    def refresh(self):
        """根据图表类型从 ReportService 拿数据 + 调用 charts.py 渲染。"""
        chart_type = self.chart_combo.currentData()
        try:
            if chart_type == "attendance_rate":
                course_id = int(self.course_edit.currentText() or 1)
                data = ReportService().attendance_rate_per_student(course_id=course_id)
                fig = chart_attendance_rate_bar(data, title=f"课程 #{course_id} 学生出勤率")
                self._render(fig, f"已渲染 {len(data)} 个学生出勤率（课程 #{course_id}）")
            elif chart_type == "attendance_trend":
                course_id = int(self.course_edit.currentText() or 1)
                data = ReportService().attendance_trend_per_course(course_id, days=DEFAULT_ATTENDANCE_DAYS)
                fig = chart_attendance_trend_line(
                    data, title=f"课程 #{course_id} 30 天出勤率趋势",
                )
                self._render(fig, f"已渲染 {len(data)} 天趋势（课程 #{course_id}）")
            elif chart_type == "lab_usage":
                lab_id = self.lab_combo.currentData()
                if lab_id is None:
                    # 不弹模态对话框（offscreen 模式下 PyQt5 模态会 hang），
                    # 改用占位图 + status label 提示。
                    fig = self._placeholder_fig("请选择一个实验室查看热力图")
                    self._render(fig, "请先选择实验室")
                    return
                data = ReportService().lab_usage_rate(lab_id, days=DEFAULT_LAB_DAYS)
                fig = chart_lab_usage_heatmap(
                    data, title=f"实验室 #{lab_id} {DEFAULT_LAB_DAYS} 天使用率热力图",
                )
                self._render(fig, f"已渲染 {len(data)} 个 (date, hour) 数据点")
            elif chart_type == "absent_warning":
                threshold = self.threshold_combo.currentData()
                data = ReportService().absent_warning_list(threshold=threshold)
                fig = chart_absent_warning_table(
                    data, title=f"缺勤预警名单（出勤率 < {int(threshold * 100)}%）",
                )
                self._render(fig, f"已渲染 {len(data)} 个预警学生")
            else:
                # 未知图表类型：占位 + status 提示
                fig = self._placeholder_fig(f"未知图表类型: {chart_type}")
                self._render(fig, f"未知图表类型: {chart_type}")
        except ValueError as e:
            # 课程 ID 解析失败：占位 + status 提示
            log.warning("课程 ID 解析失败: %s", e)
            fig = self._placeholder_fig(f"课程 ID 无效: {e}")
            self._render(fig, f"课程 ID 无效: {e}")
        except Exception as e:
            log.exception("渲染图表失败")
            fig = self._placeholder_fig(f"渲染失败: {e}")
            self._render(fig, f"渲染失败: {e}")

    def _placeholder_fig(self, message: str) -> Figure:
        """占位 Figure（避免模态对话框阻塞 + offscreen 段错误）。"""
        fig = Figure(figsize=(8, 4))
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, message, ha="center", va="center",
                fontsize=14, color="#666",
                transform=ax.transAxes)
        ax.set_xticks([]); ax.set_yticks([])
        return fig

    def _set_status(self, text: str, state: str = "neutral"):
        self.status_label.setText(text)
        self.status_label.setProperty("state", state)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
