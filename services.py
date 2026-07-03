from typing import Any

import pandas as pd


def format_currency(value: float) -> str:
    return f"¥{value:,.2f}"


def prepare_expense_rows(expenses: list[dict]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in expenses:
        rows.append(
            {
                "ID": item["id"],
                "金额": format_currency(item["amount"]),
                "分类": item["category"],
                "日期": item["date"],
                "备注": item["note"] or "-",
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
