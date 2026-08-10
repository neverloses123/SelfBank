from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from backend.app.database import Database
from backend.app.dedupe import is_duplicate, normalize_merchant


class DatabaseTests(TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / "selfbank-test.db")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_transaction_and_carrier_deduplication(self) -> None:
        invoice = self.db.create_transaction({"title": "全聯福利中心股份有限公司", "category": "日常採買", "amount": 1286, "date": "2026-08-10", "type": "expense", "source": "雲端發票"})
        bank = {"title": "信用卡消費 全聯福利中心", "category": "日常採買", "amount": 1286, "date": "2026-08-12", "type": "expense", "source": "CSV 匯入"}
        self.assertEqual(normalize_merchant(invoice["title"]), "全聯福利中心")
        self.assertTrue(is_duplicate(bank, invoice))

    def test_pdf_import_skips_duplicates(self) -> None:
        rows = [{"title": "測試商店", "category": "其他", "amount": 222, "date": "2026-08-11", "type": "expense", "source": "PDF 匯入"}]
        first = self.db.import_transactions(rows)
        second = self.db.import_transactions(rows)
        self.assertEqual(first["created_count"], 1)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["skipped_count"], 1)

    def test_transactions_can_be_pruned_to_date_range(self) -> None:
        for date_value in ("2026-06-30", "2026-07-01", "2026-08-10", "2026-08-11"):
            self.db.create_transaction({"title": date_value, "category": "餐飲", "amount": 1, "date": date_value, "type": "expense", "source": "測試"})
        self.assertEqual(self.db.prune_transactions("2026-07-01", "2026-08-10"), 2)
        self.assertEqual([row["date"] for row in self.db.list_transactions()], ["2026-08-10", "2026-07-01"])

    def test_recurring_payment_lifecycle(self) -> None:
        item = self.db.create_recurring({"title": "手機月租", "category": "帳單", "amount": 599, "day": 20, "type": "expense", "active": True})
        income = self.db.create_recurring({"title": "每月薪資", "category": "收入", "amount": 62000, "day": 8, "type": "income", "active": True})
        self.assertEqual(item["type"], "expense")
        self.assertEqual(income["type"], "income")
        self.assertTrue(item["active"])
        self.assertTrue(self.db.set_recurring_active(item["id"], False))
        self.assertTrue(any(not row["active"] for row in self.db.list_recurring()))
        self.assertTrue(self.db.delete_recurring(item["id"]))
        self.assertFalse(any(row["id"] == item["id"] for row in self.db.list_recurring()))
        self.assertFalse(self.db.delete_recurring(item["id"]))

    def test_pdf_columns_are_persisted(self) -> None:
        transaction = self.db.create_transaction({
            "title": "義美股份有限公司", "category": "其他", "amount": 69,
            "date": "2026-08-10", "type": "expense", "source": "PDF 匯入",
            "transaction_time": "2026/08/10 02:26:23", "summary": "刷卡消費",
            "expense_amount": 69, "income_amount": None, "balance": 465024,
            "note": "義美股份有限公司",
        })
        self.assertEqual(transaction["summary"], "刷卡消費")
        self.assertEqual(transaction["balance"], 465024)
        self.assertEqual(transaction["note"], "義美股份有限公司")

    def test_existing_transaction_can_be_edited_without_deleting_it(self) -> None:
        transaction = self.db.create_transaction({
            "title": "午餐", "category": "餐飲", "amount": 120,
            "date": "2026-08-10", "type": "expense", "source": "手動記帳",
        })
        updated = self.db.update_transaction(transaction["id"], {
            "title": "公司午餐", "category": "餐飲", "amount": 150,
            "date": "2026-08-10", "type": "expense", "note": "與同事聚餐",
        })
        self.assertIsNotNone(updated)
        self.assertEqual(updated["amount"], 150)
        self.assertEqual(updated["note"], "與同事聚餐")
        self.assertEqual(len(self.db.list_transactions()), 1)
        self.assertIsNone(self.db.update_transaction(999999, {
            "title": "不存在", "category": "餐飲", "amount": 1,
            "date": "2026-08-10", "type": "expense", "note": None,
        }))

    def test_reference_tables_have_requested_values(self) -> None:
        self.assertEqual([row["name"] for row in self.db.list_categories()], ["餐飲", "日用品", "娛樂", "交通", "股票", "醫療"])
        self.assertEqual([row["name"] for row in self.db.list_transaction_types()], ["收入", "支出"])
