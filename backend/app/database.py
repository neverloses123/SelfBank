from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from typing import Any, Iterator

from .dedupe import is_duplicate


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    transaction_date TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('expense', 'income')),
    source TEXT NOT NULL,
    transaction_time TEXT,
    summary TEXT,
    expense_amount REAL,
    income_amount REAL,
    balance REAL,
    note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_match ON transactions(type, amount, transaction_date);
CREATE TABLE IF NOT EXISTS transaction_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS transaction_types (
    code TEXT PRIMARY KEY CHECK (code IN ('income', 'expense')),
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS recurring_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    charge_day INTEGER NOT NULL CHECK (charge_day BETWEEN 1 AND 28),
    type TEXT NOT NULL DEFAULT 'expense' CHECK (type IN ('expense', 'income')),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_recurring_active_day ON recurring_payments(active, charge_day);
"""


class Database:
    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(recurring_payments)").fetchall()}
            if "type" not in columns:
                connection.execute("ALTER TABLE recurring_payments ADD COLUMN type TEXT NOT NULL DEFAULT 'expense' CHECK (type IN ('expense', 'income'))")
            transaction_columns = {row[1] for row in connection.execute("PRAGMA table_info(transactions)").fetchall()}
            for name, column_type in (("transaction_time", "TEXT"), ("summary", "TEXT"), ("expense_amount", "REAL"), ("income_amount", "REAL"), ("balance", "REAL"), ("note", "TEXT")):
                if name not in transaction_columns:
                    connection.execute(f"ALTER TABLE transactions ADD COLUMN {name} {column_type}")
            connection.executemany(
                "INSERT OR IGNORE INTO transaction_categories(name, sort_order) VALUES (?, ?)",
                [(name, index) for index, name in enumerate(("餐飲", "日用品", "娛樂", "交通", "股票", "醫療"), start=1)],
            )
            connection.executemany(
                "INSERT OR IGNORE INTO transaction_types(code, name) VALUES (?, ?)",
                [("income", "收入"), ("expense", "支出")],
            )
            connection.execute("UPDATE transactions SET category = '日用品' WHERE category IN ('日常採買', '帳單', '其他')")
            connection.execute("UPDATE transactions SET category = '娛樂' WHERE category = '學習'")
            connection.execute("UPDATE transactions SET category = '股票' WHERE category = '收入'")
            connection.execute("PRAGMA optimize")

    def health_check(self) -> dict[str, str]:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()
        return {"status": "connected", "backend": "sqlite", "database": self.path}

    def list_transactions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, title, category, amount, transaction_date AS date, type, source, transaction_time, summary, expense_amount, income_amount, balance, note FROM transactions ORDER BY transaction_date DESC, transaction_time DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_categories(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT id, name, sort_order FROM transaction_categories ORDER BY sort_order").fetchall()
        return [dict(row) for row in rows]

    def list_transaction_types(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT code, name FROM transaction_types ORDER BY CASE code WHEN 'income' THEN 1 ELSE 2 END").fetchall()
        return [dict(row) for row in rows]

    def create_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO transactions(title, category, amount, transaction_date, type, source, transaction_time, summary, expense_amount, income_amount, balance, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (transaction["title"], transaction["category"], transaction["amount"], transaction["date"], transaction["type"], transaction["source"], transaction.get("transaction_time"), transaction.get("summary"), transaction.get("expense_amount"), transaction.get("income_amount"), transaction.get("balance"), transaction.get("note")),
            )
            row = connection.execute(
                "SELECT id, title, category, amount, transaction_date AS date, type, source, transaction_time, summary, expense_amount, income_amount, balance, note FROM transactions WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        return dict(row)

    def update_transaction(self, item_id: int, transaction: dict[str, Any]) -> dict[str, Any] | None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE transactions SET title = ?, category = ?, amount = ?, transaction_date = ?, type = ?, note = ? WHERE id = ?",
                (transaction["title"], transaction["category"], transaction["amount"], transaction["date"], transaction["type"], transaction.get("note"), item_id),
            )
            if cursor.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT id, title, category, amount, transaction_date AS date, type, source, transaction_time, summary, expense_amount, income_amount, balance, note FROM transactions WHERE id = ?",
                (item_id,),
            ).fetchone()
        return dict(row)

    def import_transactions(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        existing = self.list_transactions(limit=10_000)
        accepted: list[dict[str, Any]] = []
        skipped = 0
        for candidate in candidates:
            date.fromisoformat(candidate["date"])
            if any(is_duplicate(candidate, item) for item in [*existing, *accepted]):
                skipped += 1
            else:
                accepted.append(candidate)
        created = [self.create_transaction(item) for item in accepted]
        return {"created": created, "created_count": len(created), "skipped_count": skipped}

    def list_recurring(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id, title, category, amount, charge_day AS day, type, active FROM recurring_payments ORDER BY active DESC, charge_day, id"
            ).fetchall()
        return [{**dict(row), "active": bool(row["active"])} for row in rows]

    def create_recurring(self, item: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO recurring_payments(title, category, amount, charge_day, type, active) VALUES (?, ?, ?, ?, ?, ?)",
                (item["title"], item["category"], item["amount"], item["day"], item.get("type", "expense"), int(item.get("active", True))),
            )
            row = connection.execute(
                "SELECT id, title, category, amount, charge_day AS day, type, active FROM recurring_payments WHERE id = ?",
                (cursor.lastrowid,),
            ).fetchone()
        result = dict(row)
        result["active"] = bool(result["active"])
        return result

    def set_recurring_active(self, item_id: int, active: bool) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("UPDATE recurring_payments SET active = ? WHERE id = ?", (int(active), item_id))
        return cursor.rowcount == 1
