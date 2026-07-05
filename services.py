from typing import Any

import pandas as pd


def format_currency(value: float) -> str:
    return f"¥{value:,.2f}"


def prepare_expense_rows(expenses: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in expenses:
        # 根据收支类型调整显示的金额：收入为正，支出显示为负
        try:
            amt = float(item.get("amount", 0.0))
        except Exception:
            amt = 0.0
        # 这里只用于显示：支出用括号表示负数，收入用正常正数表示
        if amt < 0:
            display_amount = f"({format_currency(abs(amt))})"
        else:
            display_amount = format_currency(amt)

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
