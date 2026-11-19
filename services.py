"""数据展示辅助：金额格式化、列表/统计 DataFrame 与样式。"""
from typing import Any

import pandas as pd

from models import CATEGORY_EMOJI, PAYMENT_COLORS

# 参考色板（浅色模式）：收入绿、支出红
C_INCOME = "#0ca30c"
C_EXPENSE = "#e34948"


def format_currency(value: float) -> str:
    return f"¥{value:,.2f}"


def format_signed_currency(value: float) -> str:
    """支出显示为 −¥xx.xx，收入显示为 ¥xx.xx。"""
    if value < 0:
        return f"−¥{abs(value):,.2f}"
    return format_currency(value)


def prepare_expense_rows(expenses: list[dict]) -> list[dict[str, Any]]:
    """兼容旧调用：把账目列表转成展示行（金额按类型带符号）。"""
    rows: list[dict[str, Any]] = []
    for item in expenses:
        try:
            amt = float(item.get("amount", 0.0))
        except (TypeError, ValueError):
            amt = 0.0
        display_amount = f"({format_currency(abs(amt))})" if amt < 0 else format_currency(amt)
        rows.append(
            {
                "ID": item["id"],
                "金额": display_amount,
                "类型": item.get("transaction_type", "支出"),
                "支付方式": item.get("payment_method", "支付宝"),
                "分类": item.get("category", "其他"),
                "日期": item.get("date"),
                "备注": item.get("note") or "-",
            }
        )
    return rows


def prepare_stats_dataframe(stats: list[dict]) -> pd.DataFrame:
    if not stats:
        return pd.DataFrame(columns=["分类", "总额"])

    rows = []
    for item in stats:
        rows.append({"分类": item["category"], "总额": float(item["total"])})

    return pd.DataFrame(rows)


def expense_list_frame(expenses: list[dict]) -> pd.DataFrame:
    """账目列表展示 DataFrame（金额保留符号，供样式上色）。"""
    rows = []
    for item in expenses:
        try:
            amt = float(item.get("amount", 0.0))
        except (TypeError, ValueError):
            amt = 0.0
        category = item.get("category", "其他")
        subcategory = item.get("subcategory") or ""
        label = f"{subcategory}~{category}" if subcategory else category
        emoji = CATEGORY_EMOJI.get(subcategory) or CATEGORY_EMOJI.get(category, "📦")
        rows.append(
            {
                "ID": item["id"],
                "日期": item.get("date"),
                "分类": f"{emoji} {label}",
                "金额": amt,
                "收支类型": item.get("transaction_type", "支出"),
                "支付方式": item.get("payment_method", "支付宝"),
                "备注": item.get("note") or "",
            }
        )
    return pd.DataFrame(rows)


def style_expense_list(df: pd.DataFrame):
    """账目列表样式：支出红、收入绿，支付方式用品牌色。"""
    def _amount_style(value: Any) -> str:
        if isinstance(value, (int, float)) and value < 0:
            return f"color: {C_EXPENSE}; font-weight: 600;"
        return f"color: {C_INCOME}; font-weight: 600;"

    def _payment_style(value: Any) -> str:
        color = PAYMENT_COLORS.get(value)
        return f"color: {color}; font-weight: 600;" if color else ""

    return (
        df.style
        .map(_amount_style, subset=["金额"])
        .map(_payment_style, subset=["支付方式"])
        .format({"金额": format_signed_currency}, na_rep="-")
    )


def monthly_trend_frame(year: int, rows: list[dict]) -> pd.DataFrame:
    """把某年各月收支趋势补全为 1~12 月的 DataFrame。"""
    by_month = {int(r["month"]): r for r in rows}
    data = []
    for m in range(1, 13):
        r = by_month.get(m)
        data.append(
            {
                "月份": f"{m}月",
                "收入": float(r["income"] or 0) if r else 0.0,
                "支出": float(r["expense"] or 0) if r else 0.0,
            }
        )
    return pd.DataFrame(data)


def stats_table_frame(rows: list[dict], name_key: str, emoji_map: dict | None = None) -> pd.DataFrame:
    """统计表 DataFrame：项目 / 笔数 / 总额 / 占比。"""
    grand = sum(float(r.get("total") or 0) for r in rows) or 1.0
    data = []
    for r in rows:
        name = r[name_key]
        label = f"{emoji_map.get(name, '📦')} {name}" if emoji_map else name
        data.append(
            {
                "项目": label,
                "笔数": int(r.get("count") or 0),
                "总额": float(r.get("total") or 0),
                "占比": float(r.get("total") or 0) / grand,
            }
        )
    return pd.DataFrame(data)
