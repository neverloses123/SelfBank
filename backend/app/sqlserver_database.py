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
        transaction_time NVARCHAR(30) NULL,
        summary NVARCHAR(80) NULL,
        expense_amount DECIMAL(18,2) NULL,
        income_amount DECIMAL(18,2) NULL,
        balance DECIMAL(18,2) NULL,
        note NVARCHAR(200) NULL,
        created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
END;
IF COL_LENGTH('dbo.transactions', 'transaction_time') IS NULL ALTER TABLE dbo.transactions ADD transaction_time NVARCHAR(30) NULL;
IF COL_LENGTH('dbo.transactions', 'summary') IS NULL ALTER TABLE dbo.transactions ADD summary NVARCHAR(80) NULL;
IF COL_LENGTH('dbo.transactions', 'expense_amount') IS NULL ALTER TABLE dbo.transactions ADD expense_amount DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.transactions', 'income_amount') IS NULL ALTER TABLE dbo.transactions ADD income_amount DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.transactions', 'balance') IS NULL ALTER TABLE dbo.transactions ADD balance DECIMAL(18,2) NULL;
IF COL_LENGTH('dbo.transactions', 'note') IS NULL ALTER TABLE dbo.transactions ADD note NVARCHAR(200) NULL;
IF OBJECT_ID('dbo.transaction_categories', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.transaction_categories (
        id INT IDENTITY(1,1) PRIMARY KEY,
        name NVARCHAR(40) NOT NULL UNIQUE,
        sort_order TINYINT NOT NULL UNIQUE
    );
END;
IF OBJECT_ID('dbo.transaction_types', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.transaction_types (
        code VARCHAR(10) PRIMARY KEY CHECK (code IN ('income', 'expense')),
        name NVARCHAR(10) NOT NULL UNIQUE
    );
END;
IF NOT EXISTS (SELECT 1 FROM dbo.transaction_categories)
    INSERT INTO dbo.transaction_categories(name, sort_order) VALUES (N'餐飲',1),(N'日用品',2),(N'娛樂',3),(N'交通',4),(N'股票',5),(N'醫療',6);
IF NOT EXISTS (SELECT 1 FROM dbo.transaction_types)
    INSERT INTO dbo.transaction_types(code, name) VALUES ('income',N'收入'),('expense',N'支出');
UPDATE dbo.transactions SET category = N'日用品' WHERE category IN (N'日常採買', N'帳單', N'其他');
UPDATE dbo.transactions SET category = N'娛樂' WHERE category = N'學習';
UPDATE dbo.transactions SET category = N'股票' WHERE category = N'收入';
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

SCHEMA_COMMENTS: dict[str, tuple[str, dict[str, str]]] = {
    "transactions": (
        "交易紀錄：保存所有收入與支出",
        {
            "id": "交易編號（系統自動產生）",
            "title": "名稱／交易對象",
            "category": "分類，例如餐飲、交通或醫療",
            "amount": "交易金額（正數）",
            "transaction_date": "交易日期",
            "type": "類型：income 為收入，expense 為支出",
            "source": "資料來源，例如 PDF 匯入或手動記帳",
            "transaction_time": "銀行紀錄中的交易時間",
            "summary": "銀行紀錄中的交易摘要",
            "expense_amount": "銀行紀錄中的支出金額",
            "income_amount": "銀行紀錄中的存入／收入金額",
            "balance": "該筆交易完成後的即時餘額",
            "note": "銀行紀錄附註或補充說明",
            "created_at": "資料建立時間（UTC）",
        },
    ),
    "transaction_categories": (
        "交易分類參照表",
        {
            "id": "分類編號（系統自動產生）",
            "name": "分類中文名稱",
            "sort_order": "分類顯示順序",
        },
    ),
    "transaction_types": (
        "交易類型參照表",
        {
            "code": "類型代碼：income 或 expense",
            "name": "類型中文名稱：收入或支出",
        },
    ),
    "recurring_payments": (
        "每月固定收入與固定支出",
        {
            "id": "固定收支編號（系統自動產生）",
            "title": "固定收支名稱",
            "category": "固定收支分類",
            "amount": "每月固定金額",
            "charge_day": "每月入帳或扣款日（1 至 28 日）",
            "type": "類型：income 為固定收入，expense 為固定支出",
            "active": "是否啟用：1 為啟用，0 為停用",
            "created_at": "資料建立時間（UTC）",
        },
    ),
}


def apply_schema_comments(connection: pyodbc.Connection) -> None:
    for table_name, (table_description, columns) in SCHEMA_COMMENTS.items():
        table_exists = connection.execute(
            "SELECT 1 FROM sys.extended_properties WHERE class = 1 AND major_id = OBJECT_ID(?) AND minor_id = 0 AND name = N'MS_Description'",
            f"dbo.{table_name}",
        ).fetchone()
        table_procedure = "sp_updateextendedproperty" if table_exists else "sp_addextendedproperty"
        connection.execute(
            f"EXEC sys.{table_procedure} @name=N'MS_Description', @value=?, @level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=?",
            table_description,
            table_name,
        )
        for column_name, description in columns.items():
            column_exists = connection.execute(
                "SELECT 1 FROM sys.extended_properties WHERE class = 1 AND major_id = OBJECT_ID(?) AND minor_id = COLUMNPROPERTY(OBJECT_ID(?), ?, 'ColumnId') AND name = N'MS_Description'",
                f"dbo.{table_name}",
                f"dbo.{table_name}",
                column_name,
            ).fetchone()
            column_procedure = "sp_updateextendedproperty" if column_exists else "sp_addextendedproperty"
            connection.execute(
                f"EXEC sys.{column_procedure} @name=N'MS_Description', @value=?, @level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=?, @level2type=N'COLUMN', @level2name=?",
                description,
                table_name,
                column_name,
            )


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
            apply_schema_comments(connection)

    def health_check(self) -> dict[str, str]:
        with self.connect() as connection:
            cursor = connection.execute("SELECT DB_NAME() AS database_name")
            database_name = str(cursor.fetchone()[0])
        return {"status": "connected", "backend": "sqlserver", "database": database_name}

    def list_transactions(self, limit: int = 200) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT TOP (?) id, title, category, CAST(amount AS float) AS amount, CONVERT(varchar(10), transaction_date, 23) AS date, type, source, transaction_time, summary, CAST(expense_amount AS float) AS expense_amount, CAST(income_amount AS float) AS income_amount, CAST(balance AS float) AS balance, note FROM dbo.transactions ORDER BY transaction_date DESC, transaction_time DESC, id DESC",
                limit,
            )
            return [self._dict(cursor, row) for row in cursor.fetchall()]

    def prune_transactions(self, from_date: str, to_date: str) -> int:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM dbo.transactions WHERE transaction_date < ? OR transaction_date > ?",
                from_date, to_date,
            )
            return cursor.rowcount

    def create_transaction(self, transaction: dict[str, Any]) -> dict[str, Any]:
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO dbo.transactions(title, category, amount, transaction_date, type, source, transaction_time, summary, expense_amount, income_amount, balance, note) OUTPUT INSERTED.id, INSERTED.title, INSERTED.category, CAST(INSERTED.amount AS float), CONVERT(varchar(10), INSERTED.transaction_date, 23), INSERTED.type, INSERTED.source, INSERTED.transaction_time, INSERTED.summary, CAST(INSERTED.expense_amount AS float), CAST(INSERTED.income_amount AS float), CAST(INSERTED.balance AS float), INSERTED.note VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                transaction["title"], transaction["category"], transaction["amount"], transaction["date"], transaction["type"], transaction["source"], transaction.get("transaction_time"), transaction.get("summary"), transaction.get("expense_amount"), transaction.get("income_amount"), transaction.get("balance"), transaction.get("note"),
            )
            row = cursor.fetchone()
            return dict(zip(("id", "title", "category", "amount", "date", "type", "source", "transaction_time", "summary", "expense_amount", "income_amount", "balance", "note"), row))

    def update_transaction(self, item_id: int, transaction: dict[str, Any]) -> dict[str, Any] | None:
        with self.connect() as connection:
            cursor = connection.execute(
                "UPDATE dbo.transactions SET title = ?, category = ?, amount = ?, transaction_date = ?, type = ?, note = ? WHERE id = ?",
                transaction["title"], transaction["category"], transaction["amount"], transaction["date"], transaction["type"], transaction.get("note"), item_id,
            )
            if cursor.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT id, title, category, CAST(amount AS float), CONVERT(varchar(10), transaction_date, 23), type, source, transaction_time, summary, CAST(expense_amount AS float), CAST(income_amount AS float), CAST(balance AS float), note FROM dbo.transactions WHERE id = ?",
                item_id,
            ).fetchone()
        return dict(zip(("id", "title", "category", "amount", "date", "type", "source", "transaction_time", "summary", "expense_amount", "income_amount", "balance", "note"), row))

    def list_categories(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.execute("SELECT id, name, sort_order FROM dbo.transaction_categories ORDER BY sort_order")
            return [self._dict(cursor, row) for row in cursor.fetchall()]

    def list_transaction_types(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            cursor = connection.execute("SELECT code, name FROM dbo.transaction_types ORDER BY CASE code WHEN 'income' THEN 1 ELSE 2 END")
            return [self._dict(cursor, row) for row in cursor.fetchall()]

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

    def delete_recurring(self, item_id: int) -> bool:
        with self.connect() as connection:
            cursor = connection.execute("DELETE FROM dbo.recurring_payments WHERE id = ?", item_id)
            return cursor.rowcount == 1
