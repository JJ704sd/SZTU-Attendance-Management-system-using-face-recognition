"""
utils/charts.py — matplotlib 图表生成

W4 Phase 4: 4 类报表图表（学生出勤率柱状 / 趋势折线 / 实验室使用率热力 / 缺勤预警表格）

设计要点:
- 函数签名统一 (data, ax=None) -> Figure，ax=None 时建新 Figure
- 输入是 src.services.report_service 的 dataclass（StudentRate 等）
- 中文字体: 显式 rcParams['font.sans-serif'] = ['Microsoft YaHei UI']
  （CLAUDE.md 警告 Windows 上 matplotlib 中文不设字体必乱码）
- 风格: 用 src.ui.styles.COLOR_* 全局色板
- 不强制 matplotlib backend（测试 offscreen 用 Agg，PyQt embed 用 Qt5Agg，
  让调用方决定）
"""
from typing import List, Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.services.report_service import (
    AbsentWarning,
    LabUsagePoint,
    StudentRate,
    TrendPoint,
)
from src.ui.styles import (
    COLOR_BG,
    COLOR_BUTTON,
    COLOR_DANGER,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    FONT_FAMILY,
)

# 模块级 rcParams：进程内全局生效。
# CLAUDE.md 警告: Windows 上 matplotlib 中文不设字体必乱码。
plt.rcParams["font.sans-serif"] = [FONT_FAMILY, "SimHei", "Microsoft YaHei"]
plt.rcParams["axes.unicode_minus"] = False  # 负号正常显示
plt.rcParams["font.family"] = "sans-serif"


def _ensure_ax(ax):
    """没给 ax 就建一个 (Figure, Axes) 配对。返回 (fig, ax)。"""
    if ax is None:
        fig, ax = plt.subplots(figsize=(8, 5), facecolor=COLOR_BG)
    else:
        fig = ax.get_figure()
    return fig, ax


def _empty_placeholder(ax, msg: str = "暂无数据"):
    """在 ax 上画一个居中提示文字。"""
    ax.text(0.5, 0.5, msg, ha="center", va="center",
            fontsize=14, color="#999999", transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])


# ====================================================
# 1. 学生出勤率柱状图
# ====================================================
def chart_attendance_rate_bar(
    data: List[StudentRate],
    ax=None,
    title: str = "学生出勤率排行",
) -> Figure:
    """柱状图：每位学生一根柱，y 轴 0-100%。

    颜色按出勤率分段:
    - >= 80%   绿 (COLOR_SUCCESS)
    - 60-80%   橙 (COLOR_WARNING)
    - < 60%    红 (COLOR_DANGER)
    """
    fig, ax = _ensure_ax(ax)

    if not data:
        _empty_placeholder(ax, "暂无学生出勤数据")
        ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")
        return fig

    # 颜色映射
    def _color(rate: float) -> str:
        if rate >= 0.8:
            return COLOR_SUCCESS
        if rate >= 0.6:
            return COLOR_WARNING
        return COLOR_DANGER

    colors = [_color(r.rate) for r in data]
    names = [r.real_name for r in data]
    rates_pct = [r.rate * 100 for r in data]

    bars = ax.bar(range(len(data)), rates_pct, color=colors,
                  edgecolor=COLOR_PRIMARY, linewidth=0.5)
    ax.set_xticks(range(len(data)))
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0, 105)
    ax.set_ylabel("出勤率 (%)", fontsize=10)
    ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--")

    # 柱顶标数值
    for bar, pct in zip(bars, rates_pct):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{pct:.0f}%", ha="center", va="bottom", fontsize=8)

    fig.tight_layout()
    return fig


# ====================================================
# 2. 出勤率趋势折线图
# ====================================================
def chart_attendance_trend_line(
    data: List[TrendPoint],
    ax=None,
    title: str = "出勤率趋势",
) -> Figure:
    """折线图：每日出勤率（0-100%），附 80% 预警线。"""
    fig, ax = _ensure_ax(ax)

    if not data:
        _empty_placeholder(ax, "暂无趋势数据")
        ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")
        return fig

    dates = [d.date for d in data]
    rates_pct = [d.rate * 100 for d in data]

    ax.plot(dates, rates_pct, color=COLOR_BUTTON, marker="o",
            linewidth=2, markersize=6, markerfacecolor=COLOR_BUTTON,
            markeredgecolor="white", label="出勤率")
    ax.fill_between(dates, rates_pct, alpha=0.2, color=COLOR_BUTTON)

    # 80% 参考线
    ax.axhline(y=80, color=COLOR_WARNING, linestyle="--", alpha=0.6,
               label="80% 预警线")

    ax.set_ylim(0, 105)
    ax.set_ylabel("出勤率 (%)", fontsize=10)
    ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", alpha=0.3, linestyle="--")
    ax.legend(loc="lower right", fontsize=9)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


# ====================================================
# 3. 实验室使用率热力图
# ====================================================
def chart_lab_usage_heatmap(
    data: List[LabUsagePoint],
    ax=None,
    title: str = "实验室使用率热力图",
) -> Figure:
    """热力图：date × hour 矩阵，颜色 = 准入次数。"""
    fig, ax = _ensure_ax(ax)

    if not data:
        _empty_placeholder(ax, "暂无准入数据")
        ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")
        return fig

    date_set = sorted({d.date for d in data})
    hour_set = sorted({d.hour for d in data})

    matrix = np.zeros((len(date_set), len(hour_set)), dtype=int)
    for d in data:
        row = date_set.index(d.date)
        col = hour_set.index(d.hour)
        matrix[row, col] = d.count

    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")
    fig.colorbar(im, ax=ax, label="准入次数", shrink=0.8)

    ax.set_xticks(range(len(hour_set)))
    ax.set_xticklabels([f"{h:02d}" for h in hour_set], fontsize=8, rotation=0)
    ax.set_yticks(range(len(date_set)))
    ax.set_yticklabels([d.strftime("%m-%d") for d in date_set], fontsize=8)
    ax.set_xlabel("小时", fontsize=10)
    ax.set_ylabel("日期", fontsize=10)
    ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")

    # 在每格标数值
    for r in range(len(date_set)):
        for c in range(len(hour_set)):
            v = matrix[r, c]
            if v > 0:
                ax.text(c, r, str(v), ha="center", va="center",
                        color="white" if v > matrix.max() / 2 else "black",
                        fontsize=8)

    fig.tight_layout()
    return fig


# ====================================================
# 4. 缺勤预警表格
# ====================================================
def chart_absent_warning_table(
    data: List[AbsentWarning],
    ax=None,
    title: str = "缺勤预警名单（出勤率 < 80%）",
) -> Figure:
    """表格图：列出出勤率低于阈值的学生。

    单元格按出勤率着色（红/黄/绿）。
    """
    fig, ax = _ensure_ax(ax)
    ax.axis("off")  # 隐藏坐标轴

    if not data:
        ax.text(0.5, 0.5, "🎉 暂无预警（所有学生出勤率 ≥ 80%）",
                ha="center", va="center", fontsize=14, color=COLOR_SUCCESS,
                transform=ax.transAxes)
        ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold")
        return fig

    headers = ["学号", "姓名", "出勤率", "课程"]
    rows = []
    for w in data:
        rows.append([
            f"#{w.student_id}",
            w.real_name,
            f"{w.rate * 100:.1f}%",
            w.course_name,
        ])

    table = ax.table(
        cellText=rows, colLabels=headers,
        loc="center", cellLoc="left",
        colWidths=[0.15, 0.25, 0.20, 0.40],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)

    # 表头
    for i in range(len(headers)):
        cell = table[(0, i)]
        cell.set_facecolor(COLOR_PRIMARY)
        cell.set_text_props(color="white", fontweight="bold")

    # 出勤率列按值着色
    for i, w in enumerate(data, start=1):
        rate_cell = table[(i, 2)]
        if w.rate < 0.5:
            rate_cell.set_facecolor("#FEE2E2")  # 红
        elif w.rate < 0.7:
            rate_cell.set_facecolor("#FEF3C7")  # 黄
        else:
            rate_cell.set_facecolor("#DCFCE7")  # 绿

    ax.set_title(title, fontsize=12, color=COLOR_PRIMARY, fontweight="bold", pad=20)
    fig.tight_layout()
    return fig
