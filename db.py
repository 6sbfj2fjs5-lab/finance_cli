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
                date TEXT NOT NULL,
                note TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def add_expense(amount: float, category: str, date: str, note: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO expenses (amount, category, date, note) VALUES (?, ?, ?, ?)",
            (amount, category, date, note),
        )
        conn.commit()


def get_expenses(month: Optional[object] = None, category: Optional[str] = None) -> list[dict]:
    query = "SELECT id, amount, category, date, note FROM expenses"
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


def get_months() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(date, 1, 7) AS month FROM expenses ORDER BY month DESC"
        ).fetchall()
        return [row["month"] for row in rows]


def get_stats() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses GROUP BY category ORDER BY total DESC"
        ).fetchall()
        return [dict(row) for row in rows]
