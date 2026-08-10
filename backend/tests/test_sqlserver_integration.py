import os
from unittest import TestCase, skipUnless

if os.getenv("SELFBANK_TEST_SQLSERVER") == "1":
    from backend.app.sqlserver_database import SqlServerDatabase


@skipUnless(os.getenv("SELFBANK_TEST_SQLSERVER") == "1", "SQL Server integration test is opt-in")
class SqlServerIntegrationTests(TestCase):
    marker = "SelfBank integration test"

    def setUp(self) -> None:
        from backend.app.sqlserver_database import SqlServerDatabase
        self.db = SqlServerDatabase(os.environ["SELFBANK_SQLSERVER_CONNECTION"])

    def tearDown(self) -> None:
        with self.db.connect() as connection:
            connection.execute("DELETE FROM dbo.transactions WHERE title = ?", self.marker)
            connection.execute("DELETE FROM dbo.recurring_payments WHERE title = ?", self.marker)

    def test_transaction_and_recurring_crud(self) -> None:
        transaction = self.db.create_transaction(
            {"title": self.marker, "category": "其他", "amount": 123, "date": "2026-08-10", "type": "expense", "source": "自動測試"}
        )
        self.assertEqual(transaction["amount"], 123)
        updated = self.db.update_transaction(transaction["id"], {
            "title": self.marker, "category": "餐飲", "amount": 321,
            "date": "2026-08-10", "type": "expense", "note": "更新測試",
        })
        self.assertIsNotNone(updated)
        self.assertEqual(updated["amount"], 321)
        self.assertEqual(updated["note"], "更新測試")
        recurring = self.db.create_recurring(
            {"title": self.marker, "category": "收入", "amount": 456, "day": 15, "type": "income", "active": True}
        )
        self.assertEqual(recurring["type"], "income")
        self.assertTrue(self.db.set_recurring_active(recurring["id"], False))
