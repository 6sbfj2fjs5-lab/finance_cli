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
        conn.commit()


def _ensure_schema(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA table_info(expenses)").fetchall()
    existing_columns = {row[1] for row in rows}
    if "transaction_type" not in existing_columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN transaction_type TEXT NOT NULL DEFAULT '支出'")
    if "payment_method" not in existing_columns:
        conn.execute("ALTER TABLE expenses ADD COLUMN payment_method TEXT NOT NULL DEFAULT '支付宝'")


def add_expense(
    amount: float,
    category: str,
    date: str,
    note: str,
    transaction_type: str,
    payment_method: str,
) -> None:
    with get_connection() as conn:
        # 根据收支类型存储金额符号：收入为正，支出为负
        try:
            amt = float(amount)
        except Exception:
            amt = 0.0
        if transaction_type == "支出":
            store_amount = -abs(amt)
        else:
            store_amount = abs(amt)

        conn.execute(
            "INSERT INTO expenses (amount, category, transaction_type, payment_method, date, note) VALUES (?, ?, ?, ?, ?, ?)",
            (store_amount, category, transaction_type, payment_method, date, note),
        )
        conn.commit()


def get_expenses(
    month: Optional[object] = None,
    category: Optional[str] = None,
    transaction_type: Optional[str] = None,
    payment_method: Optional[str] = None,
) -> list[dict]:
    query = "SELECT id, amount, category, transaction_type, payment_method, date, note FROM expenses"
    params: list[object] = []
    filters: list[str] = []

    if month is not None and month != "":
        if isinstance(month, int):
            filters.append("strftime('%m', date) = ?")
            params.append(f"{month:02d}")
        else:
            filters.append("substr(date, 1, 7) = ?")
            params.append(str(month))

    if category:
        filters.append("category = ?")
        params.append(category)

    if transaction_type:
        filters.append("transaction_type = ?")
        params.append(transaction_type)

    if payment_method:
        filters.append("payment_method = ?")
        params.append(payment_method)

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
    """Update the date of an expense by id."""
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
    with get_connection() as conn:
        # 使用绝对值统计各分类总额（支出按绝对值计）
        rows = conn.execute(
            "SELECT category, SUM(ABS(amount)) AS total FROM expenses GROUP BY category ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_type_stats() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT transaction_type AS type, SUM(ABS(amount)) AS total FROM expenses GROUP BY transaction_type ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_payment_stats() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT payment_method AS payment_method, SUM(ABS(amount)) AS total FROM expenses GROUP BY payment_method ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]
