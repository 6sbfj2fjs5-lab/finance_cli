"""导出 Excel 账单：账单明细、分类/类型/支付方式统计、月度汇总与图表。"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from io import BytesIO
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import db
from models import PAYMENT_COLORS, TYPE_COLORS, category_label

# ---- 中文字体（优先 Windows 常见字体，兼容 Linux 云端，避免图表中文显示为方框）----
_CANDIDATES = [
    # Windows
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\msyh.ttf",
    r"C:\Windows\Fonts\SimHei.ttf",
    r"C:\Windows\Fonts\SimSun.ttc",
    # Linux（Streamlit Community Cloud / 常见服务器发行版）
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKsc-Regular.otf",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/truetype/arphic/uming.ttc",
    # macOS
    "/System/Library/Fonts/PingFang.ttc",
]

_CJK_NAME_HINTS = (
    "CJK", "WenQuanYi", "Droid Sans Fallback", "YaHei", "SimHei", "SimSun",
    "PingFang", "Noto Sans SC", "Source Han",
)


def _setup_chinese_font() -> None:
    for path in _CANDIDATES:
        if os.path.exists(path):
            try:
                font_manager.fontManager.addfont(path)
                rcParams["font.sans-serif"] = [font_manager.FontProperties(fname=path).get_name()]
                return
            except Exception:
                continue
    # 兜底：扫描系统已注册字体，找能显示中文的字体
    for path in font_manager.findSystemFonts():
        try:
            name = font_manager.FontProperties(fname=path).get_name()
        except Exception:
            continue
        if any(hint.lower() in name.lower() for hint in _CJK_NAME_HINTS):
            try:
                font_manager.fontManager.addfont(path)
                rcParams["font.sans-serif"] = [name]
                return
            except Exception:
                continue
    rcParams["font.sans-serif"] = ["DejaVu Sans"]


_setup_chinese_font()
rcParams["axes.unicode_minus"] = False

# ---- 参考色板 ----
C_BLUE = "#2a78d6"
C_INK = "#0b0b0b"
C_INK_2 = "#52514e"
HEADER_FILL = "2A78D6"

_THIN = Side(style="thin", color="D8DEE8")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_BODY_FONT = Font(name="微软雅黑", size=10.5)
_HEADER_FONT = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
_HEADER_FILL = PatternFill(fill_type="solid", fgColor=HEADER_FILL)


def _write_header(ws, headers: list[str], widths: list[float]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 22
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _append_rows(ws, rows: list[list]) -> None:
    for row in rows:
        ws.append(row)
        for cell in ws[ws.max_row]:
            cell.border = _BORDER
            cell.font = _BODY_FONT


def _filter_expenses(months: Iterable[int] | None = None, year: int | None = None) -> list[dict]:
    all_expenses = db.get_expenses()
    if year is None:
        year = datetime.now().year
    if months is None:
        months = list(range(1, 13))

    months_set = set(months)
    filtered = []
    for item in all_expenses:
        date_str = item["date"]
        if len(date_str) >= 7:
            if int(date_str[:4]) == year and int(date_str[5:7]) in months_set:
                filtered.append(item)
    return filtered


def _group_stats(expenses: list[dict]) -> tuple[dict, dict, dict]:
    """返回 (分类, 类型, 支付方式) 的统计：name -> (total, count)。"""
    category_stats: dict[str, list] = {}
    type_stats: dict[str, list] = {}
    payment_stats: dict[str, list] = {}
    for item in expenses:
        amt = abs(float(item.get("amount", 0.0)))
        for pool, key in ((category_stats, "category"), (type_stats, "transaction_type"), (payment_stats, "payment_method")):
            pool.setdefault(item[key], [0.0, 0])
            pool[item[key]][0] += amt
            pool[item[key]][1] += 1
    return category_stats, type_stats, payment_stats


def export_expenses_to_excel(buffer: BytesIO, months: Iterable[int] | None = None, year: int | None = None) -> None:
    expenses = _filter_expenses(months=months, year=year)
    category_stats, type_stats, payment_stats = _group_stats(expenses)
    wb = Workbook()

    # ---- 1. 账单明细 ----
    ws_detail = wb.active
    ws_detail.title = "账单明细"
    _write_header(ws_detail, ["ID", "日期", "收支类型", "分类", "细分", "支付方式", "金额", "备注"], [7, 12, 10, 14, 10, 10, 12, 34])
    detail_rows = [
        [item["id"], item["date"], item["transaction_type"],
         category_label(item["category"], item.get("subcategory") or ""),
         item.get("subcategory") or "", item["payment_method"], round(float(item["amount"]), 2), item["note"] or ""]
        for item in expenses
    ]
    _append_rows(ws_detail, detail_rows)
    for row in ws_detail.iter_rows(min_row=2, max_row=ws_detail.max_row):
        row[6].number_format = '#,##0.00;[Red]-#,##0.00'
        row[6].alignment = Alignment(horizontal="right")

    income = sum(float(i["amount"]) for i in expenses if float(i["amount"]) > 0)
    expense = sum(-float(i["amount"]) for i in expenses if float(i["amount"]) < 0)
    start = ws_detail.max_row + 2
    summary_rows = [("收入合计", income, "0B7A1E"), ("支出合计", expense, "C0392B"), ("结余", income - expense, HEADER_FILL)]
    for idx, (label, value, color) in enumerate(summary_rows):
        r = start + idx
        ws_detail.cell(r, 1, label).font = Font(name="微软雅黑", size=10.5, bold=True, color=color)
        cell = ws_detail.cell(r, 7, round(value, 2))
        cell.number_format = '#,##0.00;[Red]-#,##0.00'
        cell.font = Font(name="微软雅黑", size=10.5, bold=True, color=color)
        cell.alignment = Alignment(horizontal="right")

    # ---- 2. 分类统计 ----
    _add_group_sheet(wb, "分类统计", "分类", category_stats)
    # ---- 3. 类型统计 ----
    _add_group_sheet(wb, "类型统计", "类型", type_stats)
    # ---- 4. 支付方式统计 ----
    _add_group_sheet(wb, "支付方式统计", "支付方式", payment_stats)

    # ---- 5. 月度汇总 ----
    _add_monthly_sheet(wb, expenses)

    # ---- 6. 统计图 ----
    _add_chart_sheet(wb, category_stats, type_stats, payment_stats, expenses)

    wb.save(buffer)


def _add_group_sheet(wb: Workbook, title: str, entity_label: str, stats: dict[str, list]) -> None:
    ws = wb.create_sheet(title)
    _write_header(ws, [entity_label, "笔数", "总额", "占比"], [16, 10, 14, 10])
    grand = sum(v[0] for v in stats.values()) or 1.0
    for name, (total, count) in sorted(stats.items(), key=lambda kv: -kv[1][0]):
        _append_rows(ws, [[name, count, round(total, 2), total / grand]])
        row = ws.max_row
        ws.cell(row, 2).alignment = Alignment(horizontal="center")
        ws.cell(row, 3).number_format = '#,##0.00'
        ws.cell(row, 3).alignment = Alignment(horizontal="right")
        ws.cell(row, 4).number_format = '0.0%'
        ws.cell(row, 4).alignment = Alignment(horizontal="center")
    # 合计行
    _append_rows(ws, [["合计", sum(v[1] for v in stats.values()), round(grand, 2), 1.0]])
    total_row = ws.max_row
    for cell in ws[total_row]:
        cell.font = Font(name="微软雅黑", size=10.5, bold=True)
        cell.fill = PatternFill(fill_type="solid", fgColor="F2F6FC")
    ws.cell(total_row, 3).number_format = '#,##0.00'
    ws.cell(total_row, 3).alignment = Alignment(horizontal="right")
    ws.cell(total_row, 4).number_format = '0.0%'
    ws.cell(total_row, 4).alignment = Alignment(horizontal="center")


def _add_monthly_sheet(wb: Workbook, expenses: list[dict]) -> None:
    ws = wb.create_sheet("月度汇总")
    _write_header(ws, ["月份", "收入", "支出", "结余", "笔数"], [12, 14, 14, 14, 10])
    by_month: dict[str, list] = {}
    for item in expenses:
        month = item["date"][:7]
        amt = float(item["amount"])
        entry = by_month.setdefault(month, [0.0, 0.0, 0])
        if amt >= 0:
            entry[0] += amt
        else:
            entry[1] += -amt
        entry[2] += 1
    for month in sorted(by_month):
        income_m, expense_m, count = by_month[month]
        _append_rows(ws, [[month, round(income_m, 2), round(expense_m, 2), round(income_m - expense_m, 2), count]])
        row = ws.max_row
        for col in (2, 3, 4):
            ws.cell(row, col).number_format = '#,##0.00'
            ws.cell(row, col).alignment = Alignment(horizontal="right")
        ws.cell(row, 5).alignment = Alignment(horizontal="center")


def _add_chart_sheet(wb: Workbook, category_stats, type_stats, payment_stats, expenses: list[dict]) -> None:
    ws = wb.create_sheet("统计图")
    _write_header(ws, ["图表", "说明"], [42, 42])

    # 月度趋势数据
    trend: dict[str, tuple[float, float]] = {}
    for item in expenses:
        month = item["date"][5:7] + "月"
        amt = float(item["amount"])
        inc, exp = trend.get(month, (0.0, 0.0))
        trend[month] = (inc + max(amt, 0), exp + max(-amt, 0))

    bar_path = _create_chart_image(
        {k: v[0] for k, v in category_stats.items()}, chart_type="bar", title="分类金额排行"
    )
    type_path = _create_chart_image(
        {k: v[0] for k, v in type_stats.items()}, chart_type="pie", title="收支类型分布", colors=TYPE_COLORS
    )
    payment_path = _create_chart_image(
        {k: v[0] for k, v in payment_stats.items()}, chart_type="pie", title="支付方式分布", colors=PAYMENT_COLORS
    )
    trend_path = _create_chart_image(trend, chart_type="trend", title="月度收支趋势")

    try:
        _place_image(ws, bar_path, "A3", 640)
        _place_image(ws, type_path, "H3", 380)
        _place_image(ws, payment_path, "H21", 380)
        _place_image(ws, trend_path, "A24", 640)
        for row, text in ((3, "分类金额排行（柱状图）"), (21, "支付方式分布（饼图）"), (24, "月度收支趋势（柱状图）")):
            cell = ws.cell(row, 2, text)
            cell.font = Font(name="微软雅黑", size=9, color="808080")
    finally:
        for path in (bar_path, type_path, payment_path, trend_path):
            if os.path.exists(path):
                os.remove(path)


def _place_image(ws, path: str, anchor: str, width: int) -> None:
    img = Image(path)
    ratio = img.height / img.width
    img.width = width
    img.height = int(width * ratio)
    ws.add_image(img, anchor)


def _create_chart_image(stats: dict, chart_type: str, title: str, colors: dict | None = None) -> str:
    """用 matplotlib 生成图表 PNG，返回临时文件路径。"""
    labels = list(stats.keys())
    values = list(stats.values())
    if chart_type == "bar":
        fig, ax = plt.subplots(figsize=(7.6, max(3.4, 0.34 * len(labels) + 1.2)))
        pairs = sorted(zip(labels, values), key=lambda p: p[1])
        bars = ax.barh([p[0] for p in pairs], [p[1] for p in pairs], color=C_BLUE, height=0.62)
        ax.bar_label(bars, fmt="¥%.0f", padding=3, fontsize=8.5, color=C_INK_2)
        ax.set_xlabel("金额（元）", fontsize=9.5)
        ax.xaxis.grid(True, color="#e1e0d9", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="both", labelsize=9.5)
    elif chart_type == "pie":
        fig, ax = plt.subplots(figsize=(4.6, 3.4))
        if not values:
            ax.text(0.5, 0.5, "无数据", ha="center", va="center", fontsize=11, color=C_INK_2)
        else:
            color_list = [colors.get(l, "#9ec5f4") for l in labels] if colors else None
            wedges, _texts, autotexts = ax.pie(
                values,
                labels=labels,
                colors=color_list,
                autopct="%.1f%%",
                startangle=90,
                pctdistance=0.72,
                wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5),
                textprops=dict(fontsize=9.5),
            )
            for t in autotexts:
                t.set_color("white")
                t.set_fontsize(9)
    elif chart_type == "trend":
        fig, ax = plt.subplots(figsize=(7.6, 3.6))
        months = sorted(labels, key=lambda m: int(m.rstrip("月")))
        x = range(len(months))
        width = 0.36
        income_vals = [stats[m][0] for m in months]
        expense_vals = [stats[m][1] for m in months]
        ax.bar([i - width / 2 for i in x], income_vals, width=width, color="#0ca30c", label="收入")
        ax.bar([i + width / 2 for i in x], expense_vals, width=width, color="#e34948", label="支出")
        ax.set_xticks(list(x))
        ax.set_xticklabels(months, fontsize=9)
        ax.legend(fontsize=9, frameon=False)
        ax.yaxis.grid(True, color="#e1e0d9", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
    else:
        fig, ax = plt.subplots(figsize=(4.6, 3.4))
        ax.text(0.5, 0.5, "无数据", ha="center", va="center")

    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    ax.set_title(title, fontsize=12, color=C_INK, pad=12)
    fig.tight_layout()

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        path = temp_file.name
    fig.savefig(path, format="png", dpi=150)
    plt.close(fig)
    return path
