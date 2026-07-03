from __future__ import annotations

import os
import tempfile
from io import BytesIO
from typing import Iterable

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.drawing.image import Image
from openpyxl.styles import Font, PatternFill

import db


def _filter_expenses(months: Iterable[int] | None = None, year: int | None = None) -> list[dict]:
    all_expenses = db.get_expenses()
    if year is None:
        year = 2026

    if months is None:
        months = list(range(1, 13))

    months_set = set(months)
    filtered = []
    for item in all_expenses:
        date_str = item["date"]
        if len(date_str) >= 7:
            expense_year = int(date_str[:4])
            expense_month = int(date_str[5:7])
            if expense_year == year and expense_month in months_set:
                filtered.append(item)
    return filtered


def export_expenses_to_excel(buffer: BytesIO, months: Iterable[int] | None = None, year: int | None = None) -> None:
    expenses = _filter_expenses(months=months, year=year)
    wb = Workbook()
    ws_detail = wb.active
    ws_detail.title = "账单明细"
    ws_detail.append(["ID", "金额", "分类", "日期", "备注"])
    for item in expenses:
        ws_detail.append([item["id"], item["amount"], item["category"], item["date"], item["note"] or ""])

    stats = {}
    for item in expenses:
        stats[item["category"]] = stats.get(item["category"], 0.0) + float(item["amount"])

    ws_stats = wb.create_sheet("分类统计")
    ws_stats.append(["分类", "总额"])
    for category, total in sorted(stats.items()):
        ws_stats.append([category, total])

    ws_chart = wb.create_sheet("统计图")
    ws_chart.append(["图表", "说明"])
    ws_chart.append(["柱状图", "按分类展示支出总额"])
    ws_chart.append(["饼图", "按分类展示占比"])

    pie_path = _create_chart_image(stats, chart_type="pie")
    bar_path = _create_chart_image(stats, chart_type="bar")
    try:
        img_bar = Image(bar_path)
        img_bar.width = 6
        img_bar.height = 3.5
        ws_chart.add_image(img_bar, "A5")

        img_pie = Image(pie_path)
        img_pie.width = 6
        img_pie.height = 3.5
        ws_chart.add_image(img_pie, "G5")

        for row in ws_detail.iter_rows(min_row=1, max_row=1):
            for cell in row:
                cell.fill = PatternFill(fill_type="solid", fgColor="D9EAF7")
                cell.font = Font(bold=True)

        wb.save(buffer)
    finally:
        if os.path.exists(pie_path):
            os.remove(pie_path)
        if os.path.exists(bar_path):
            os.remove(bar_path)



def _create_chart_image(stats: dict[str, float], chart_type: str) -> str:
    labels = list(stats.keys())
    values = list(stats.values())
    fig, ax = plt.subplots(figsize=(4, 3))
    if chart_type == "bar":
        ax.bar(labels, values)
        ax.set_title("分类支出柱状图")
        ax.set_ylabel("金额")
    else:
        ax.pie(values, labels=labels, autopct="%1.1f%%")
        ax.set_title("分类支出扇形图")
    ax.set_facecolor("white")
    fig.tight_layout()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
        path = temp_file.name
    fig.savefig(path, format="png", dpi=150)
    plt.close(fig)
    return path
