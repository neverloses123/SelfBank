from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pyodbc

from .database import Database


SCHEMA = """
IF OBJECT_ID('dbo.transactions', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.transactions (
        id INT IDENTITY(1,1) PRIMARY KEY,
        title NVARCHAR(120) NOT NULL,
        category NVARCHAR(40) NOT NULL,
        amount DECIMAL(18,2) NOT NULL CHECK (amount >= 0),
        transaction_date DATE NOT NULL,
        type VARCHAR(10) NOT NULL CHECK (type IN ('expense', 'income')),
        source NVARCHAR(40) NOT NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_transactions_date' AND object_id = OBJECT_ID('dbo.transactions'))
    CREATE INDEX idx_transactions_date ON dbo.transactions(transaction_date DESC);
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_transactions_match' AND object_id = OBJECT_ID('dbo.transactions'))
    CREATE INDEX idx_transactions_match ON dbo.transactions(type, amount, transaction_date);
IF OBJECT_ID('dbo.recurring_payments', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.recurring_payments (
        id INT IDENTITY(1,1) PRIMARY KEY,
        title NVARCHAR(120) NOT NULL,
        category NVARCHAR(40) NOT NULL,
        amount DECIMAL(18,2) NOT NULL CHECK (amount > 0),
        charge_day TINYINT NOT NULL CHECK (charge_day BETWEEN 1 AND 28),
        type VARCHAR(10) NOT NULL DEFAULT 'expense' CHECK (type IN ('expense', 'income')),
        active BIT NOT NULL DEFAULT 1,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
IF COL_LENGTH('dbo.recurring_payments', 'type') IS NULL
    ALTER TABLE dbo.recurring_payments ADD type VARCHAR(10) NOT NULL CONSTRAINT DF_recurring_payments_type DEFAULT 'expense' WITH VALUES;
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'idx_recurring_active_day' AND object_id = OBJECT_ID('dbo.recurring_payments'))
    CREATE INDEX idx_recurring_active_day ON dbo.recurring_payments(active, charge_day);
"""


class SqlServerDatabase(Database):
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[pyodbc.Connection]:
        connection = pyodbc.connect(self.connection_string, timeout=10)
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _dict(cursor: pyodbc.Cursor, row: pyodbc.Row) -> dict[str, Any]:
        return dict(zip((column[0] for column in cursor.description), row))

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute(SCHEMA)

    def list_transactions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT TOP (?) id, title, category, CAST(amount AS float) AS amount, CONVERT(varchar(10), transaction_date, 23) AS date, type, source FROM dbo.transactions ORDER BY transaction_date DESC, id DESC",
                limit,
            )
            return [self._dict(cursor, row) for row in cursor.fetchall()]

    def create_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO dbo.transactions(title, category, amount, transaction_date, type, source) OUTPUT INSERTED.id, INSERTED.title, INSERTED.category, CAST(INSERTED.amount AS float), CONVERT(varchar(10), INSERTED.transaction_date, 23), INSERTED.type, INSERTED.source VALUES (?, ?, ?, ?, ?, ?)",
                transaction["title"], transaction["category"], transaction["amount"], transaction["date"], transaction["type"], transaction["source"],
            )
            row = cursor.fetchone()
            return dict(zip(("id", "title", "category", "amount", "date", "type", "source"), row))

    def list_recurring(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT id, title, category, CAST(amount AS float) AS amount, charge_day AS day, type, active FROM dbo.recurring_payments ORDER BY active DESC, charge_day, id"
            )
            rows = [self._dict(cursor, row) for row in cursor.fetchall()]
        return [{**row, "active": bool(row["active"])} for row in rows]

    def create_recurring(self, item: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO dbo.recurring_payments(title, category, amount, charge_day, type, active) OUTPUT INSERTED.id, INSERTED.title, INSERTED.category, CAST(INSERTED.amount AS float), INSERTED.charge_day, INSERTED.type, INSERTED.active VALUES (?, ?, ?, ?, ?, ?)",
                item["title"], item["category"], item["amount"], item["day"], item.get("type", "expense"), bool(item.get("active", True)),
            )
            row = cursor.fetchone()
        result = dict(zip(("id", "title", "category", "amount", "day", "type", "active"), row))
        result["active"] = bool(result["active"])
        return result

    def set_recurring_active(self, item_id: int, active: bool) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("UPDATE dbo.recurring_payments SET active = ? WHERE id = ?", bool(active), item_id)
            return cursor.rowcount == 1
