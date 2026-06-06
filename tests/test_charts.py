"""
tests/test_charts.py — utils/charts.py 单测

W4 Phase 4 验收:
- 4 个图表函数都生成 Figure 不挂
- 空数据不挂
- 接受外部 ax
- 中文字体设置正确（CLAUDE.md 警告 Windows 上 matplotlib 中文不设字体必乱码）
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest

from src.utils.charts import (
    chart_absent_warning_table,
    chart_attendance_rate_bar,
    chart_attendance_trend_line,
    chart_lab_usage_heatmap,
)
from src.services.report_service import (
    AbsentWarning,
    LabUsagePoint,
    StudentRate,
    TrendPoint,
)
from src.ui.styles import FONT_FAMILY


def test_chinese_font_configured_at_module_load():
    """utils.charts 加载时已设中文字体（CLAUDE.md 警告 Windows 必设）"""
    import src.utils.charts  # noqa: F401  触发 module-level rcParams
    assert FONT_FAMILY in plt.rcParams["font.sans-serif"]
    assert plt.rcParams["axes.unicode_minus"] is False


def test_chart_attendance_rate_bar_renders():
    """学生出勤率柱状图不挂"""
    data = [
        StudentRate(student_id=1, real_name="张三", rate=0.95),
        StudentRate(student_id=2, real_name="李四", rate=0.75),
        StudentRate(student_id=3, real_name="王五", rate=0.20),
    ]
    fig = chart_attendance_rate_bar(data, title="测试柱状图")
    try:
        assert fig is not None
        # Figure 应该有 1 个 Axes
        axes = fig.get_axes()
        assert len(axes) >= 1
    finally:
        plt.close(fig)


def test_chart_attendance_trend_line_renders():
    """出勤率趋势折线图不挂"""
    from datetime import date
    data = [
        TrendPoint(date=date(2026, 6, 1), rate=0.85),
        TrendPoint(date=date(2026, 6, 2), rate=0.90),
        TrendPoint(date=date(2026, 6, 3), rate=0.78),
    ]
    fig = chart_attendance_trend_line(data, title="测试折线图")
    try:
        assert fig is not None
    finally:
        plt.close(fig)


def test_chart_lab_usage_heatmap_renders():
    """实验室使用率热力图不挂"""
    from datetime import date
    data = [
        LabUsagePoint(date=date(2026, 6, 1), hour=9, count=3),
        LabUsagePoint(date=date(2026, 6, 1), hour=10, count=5),
        LabUsagePoint(date=date(2026, 6, 2), hour=10, count=4),
    ]
    fig = chart_lab_usage_heatmap(data, title="测试热力图")
    try:
        assert fig is not None
    finally:
        plt.close(fig)


def test_chart_absent_warning_table_renders():
    """缺勤预警表格不挂"""
    data = [
        AbsentWarning(student_id=1, real_name="张三", rate=0.20, course_name="（全部课程）"),
        AbsentWarning(student_id=2, real_name="李四", rate=0.65, course_name="（全部课程）"),
    ]
    fig = chart_absent_warning_table(data, title="测试表格")
    try:
        assert fig is not None
    finally:
        plt.close(fig)


def test_charts_handle_empty_data():
    """4 个图表函数空数据不挂（边界条件）"""
    chart_attendance_rate_bar([])
    chart_attendance_trend_line([])
    chart_lab_usage_heatmap([])
    chart_absent_warning_table([])


def test_charts_accept_external_ax():
    """4 个图表都接受外部 ax（PyQt5 嵌入场景需要）"""
    data = [StudentRate(student_id=1, real_name="测试", rate=0.5)]
    fig, ax = plt.subplots()
    try:
        # 接受 ax 后应返回同一个 fig
        fig_back = chart_attendance_rate_bar(data, ax=ax, title="外部 ax")
        assert fig_back is fig
    finally:
        plt.close(fig)
