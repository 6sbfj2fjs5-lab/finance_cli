"""SQLite 数据层：建表、增删改查与统计。"""
import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).resolve().parent / "finance.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                transaction_type TEXT NOT NULL DEFAULT '支出',
                payment_method TEXT NOT NULL DEFAULT '支付宝',
                date TEXT NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_schema(conn)
        _migrate_legacy_subcategories(conn)
        conn.commit()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(expenses)").fetchall()
    existing_columns = {row[1] for row in rows}
    if "transaction_type" not in existing_columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN transaction_type TEXT NOT NULL DEFAULT '支出'")
    if "payment_method" not in existing_columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT NOT NULL DEFAULT '支付宝'")
    if "subcategory" not in existing_columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN subcategory TEXT NOT NULL DEFAULT ''")


def _migrate_legacy_subcategories(conn: sqlite3.Connection) -> None:
    """旧数据迁移：原独立分类若已成为某大类的子分类，归入该大类（幂等）。"""
    from models import CATEGORY_SUBCATEGORIES

    for parent, subs in CATEGORY_SUBCATEGORIES.items():
        for sub in subs:
            conn.execute(
                "UPDATE expenses SET category = ?, subcategory = ? "
                "WHERE category = ? AND (subcategory = '' OR subcategory IS NULL)",
                (parent, sub, sub),
            )


def _signed_amount(amount: float, transaction_type: str) -> float:
    """按收支类型存储金额符号：支出为负、收入为正。"""
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        amt = 0.0
    return -abs(amt) if transaction_type == "支出" else abs(amt)


def add_expense(
    amount: float,
    category: str,
    date: str,
    note: str,
    transaction_type: str = "支出",
    payment_method: str = "支付宝",
    subcategory: str = "",
) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (amount, category, subcategory, transaction_type, payment_method, date, note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                _signed_amount(amount, transaction_type),
                category,
                subcategory,
                transaction_type,
                payment_method,
                date,
                note,
            ),
        )
        conn.commit()


def update_expense(
    expense_id: int,
    amount: float,
    category: str,
    transaction_type: str,
    payment_method: str,
    date: str,
    note: str,
    subcategory: str = "",
) -> None:
    """完整更新一条账目（金额按收支类型重算符号）。"""
    with get_connection() as conn:
        conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, subcategory = ?, transaction_type = ?, "
            "payment_method = ?, date = ?, note = ? WHERE id = ?",
            (
                _signed_amount(amount, transaction_type),
                category,
                subcategory,
                transaction_type,
                payment_method,
                date,
                note,
                expense_id,
            ),
        )
        conn.commit()


def get_expenses(
    month: Optional[object] = None,
    year: Optional[int] = None,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    payment_method: Optional[str] = None,
    subcategory: Optional[str] = None,
    date_str: Optional[str] = None,
) -> list[dict]:
    query = (
        "SELECT id, amount, category, subcategory, transaction_type, payment_method, date, note "
        "FROM expenses"
    )
    params: list[object] = []
    filters: list[str] = []

    if month is not None and month != "":
        if isinstance(month, int):
            filters.append("strftime('%m', date) = ?")
            params.append(f"{month:02d}")
        else:
            filters.append("substr(date, 1, 7) = ?")
            params.append(str(month))

    if year:
        filters.append("substr(date, 1, 4) = ?")
        params.append(str(year))

    if date_str:
        filters.append("date = ?")
        params.append(date_str)

    if category:
        filters.append("category = ?")
        params.append(category)

    if transaction_type:
        filters.append("transaction_type = ?")
        params.append(transaction_type)

    if payment_method:
        filters.append("payment_method = ?")
        params.append(payment_method)

    if subcategory:
        filters.append("subcategory = ?")
        params.append(subcategory)

    if filters:
        query += " WHERE " + " AND ".join(filters)

    query += " ORDER BY date DESC, id DESC"

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def delete_expense(expense_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()


def update_expense_date(expense_id: int, new_date: str) -> None:
    """仅更新日期（兼容旧接口）。"""
    with get_connection() as conn:
        conn.execute("UPDATE expenses SET date = ? WHERE id = ?", (new_date, expense_id))
        conn.commit()


def get_months() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(date, 1, 7) AS month FROM expenses ORDER BY month DESC"
        ).fetchall()
        return [row["month"] for row in rows]


def get_stats() -> list[dict]:
    """按分类统计总额（兼容旧接口）。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, SUM(ABS(amount)) AS total FROM expenses GROUP BY category ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_category_stats() -> list[dict]:
    """按分类统计：总额 + 笔数，按总额降序。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, SUM(ABS(amount)) AS total, COUNT(*) AS count "
            "FROM expenses GROUP BY category ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_type_stats() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT transaction_type AS type, SUM(ABS(amount)) AS total, COUNT(*) AS count "
            "FROM expenses GROUP BY transaction_type ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_payment_stats() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT payment_method, SUM(ABS(amount)) AS total, COUNT(*) AS count "
            "FROM expenses GROUP BY payment_method ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_month_summary(year: int, month: int) -> dict:
    """某年某月汇总：收入、支出、结余、笔数。"""
    prefix = f"{year:04d}-{month:02d}"
    with get_connection() as conn:
        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income, "
            "SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS expense, "
            "COUNT(*) AS count "
            "FROM expenses WHERE substr(date, 1, 7) = ?",
            (prefix,),
        ).fetchone()
    income = float(row["income"] or 0)
    expense = float(row["expense"] or 0)
    return {"income": income, "expense": expense, "balance": income - expense, "count": int(row["count"] or 0)}


def get_day_summary(day: str) -> dict:
    """某天（YYYY-MM-DD）的支出总额与笔数。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS expense, "
            "COUNT(*) AS count "
            "FROM expenses WHERE date = ?",
            (day,),
        ).fetchone()
    return {"expense": float(row["expense"] or 0), "count": int(row["count"] or 0)}


def get_overall_summary() -> dict:
    """全部数据汇总：收入、支出、结余、笔数。"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT "
            "SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income, "
            "SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS expense, "
            "COUNT(*) AS count "
            "FROM expenses"
        ).fetchone()
    income = float(row["income"] or 0)
    expense = float(row["expense"] or 0)
    return {"income": income, "expense": expense, "balance": income - expense, "count": int(row["count"] or 0)}


def get_monthly_trend(year: int) -> list[dict]:
    """某年各月收支趋势。"""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT substr(date, 6, 2) AS month, "
            "SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income, "
            "SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS expense "
            "FROM expenses WHERE substr(date, 1, 4) = ? "
            "GROUP BY month ORDER BY month",
            (str(year),),
        ).fetchall()
        return [dict(row) for row in rows]
