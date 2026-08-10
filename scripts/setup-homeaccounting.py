from __future__ import annotations

import os
import sys
from pathlib import Path

import pyodbc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.sqlserver_database import SCHEMA, SCHEMA_COMMENTS, apply_schema_comments


MASTER_CONNECTION = os.getenv(
    "SELFBANK_SQLSERVER_MASTER_CONNECTION",
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=master;"
    "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
)
DATABASE_CONNECTION = os.getenv(
    "SELFBANK_SQLSERVER_CONNECTION",
    "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=HomeAccounting;"
    "Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
)


def main() -> None:
    with pyodbc.connect(MASTER_CONNECTION, autocommit=True, timeout=10) as connection:
        row = connection.execute(
            "SELECT SUSER_SNAME(), IS_SRVROLEMEMBER('sysadmin'), DB_ID(N'HomeAccounting')"
        ).fetchone()
        login_name, is_sysadmin, database_id = row
        if database_id is None:
            connection.execute("CREATE DATABASE HomeAccounting")
            print("created_database=HomeAccounting")
        else:
            print("database_exists=HomeAccounting")
        print(f"login={login_name}")
        print(f"is_sysadmin={is_sysadmin}")

    with pyodbc.connect(DATABASE_CONNECTION, autocommit=False, timeout=10) as connection:
        connection.execute(SCHEMA)
        apply_schema_comments(connection)
        connection.commit()
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sys.tables WHERE name IN "
                "('transactions','transaction_categories','transaction_types','recurring_payments') "
                "ORDER BY name"
            ).fetchall()
        ]
        print("tables=" + ",".join(tables))
        expected_comments = sum(1 + len(columns) for _, columns in SCHEMA_COMMENTS.values())
        comment_count = connection.execute(
            "SELECT COUNT(*) FROM sys.extended_properties ep "
            "JOIN sys.objects o ON o.object_id = ep.major_id "
            "WHERE ep.name = N'MS_Description' AND o.name IN "
            "('transactions','transaction_categories','transaction_types','recurring_payments')"
        ).fetchone()[0]
        if comment_count != expected_comments:
            raise RuntimeError(f"欄位註解不完整：預期 {expected_comments}，實際 {comment_count}")
        print(f"schema_comments={comment_count}")
        print(f"transactions={connection.execute('SELECT COUNT(*) FROM dbo.transactions').fetchone()[0]}")
        print(f"recurring_payments={connection.execute('SELECT COUNT(*) FROM dbo.recurring_payments').fetchone()[0]}")


if __name__ == "__main__":
    main()
