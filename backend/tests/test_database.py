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

    def test_csv_import_skips_duplicates(self) -> None:
        self.db.create_transaction({"title": "全聯福利中心", "category": "日常採買", "amount": 1286, "date": "2026-08-10", "type": "expense", "source": "雲端發票"})
        content = "date,title,amount,type,category\n2026-08-12,信用卡消費 全聯福利中心,1286,expense,日常採買\n2026-08-11,測試商店,222,expense,其他\n"
        result = self.db.import_csv(content)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["skipped_count"], 1)
        second = self.db.import_csv(content)
        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["skipped_count"], 2)

    def test_recurring_payment_lifecycle(self) -> None:
        item = self.db.create_recurring({"title": "手機月租", "category": "帳單", "amount": 599, "day": 20, "type": "expense", "active": True})
        income = self.db.create_recurring({"title": "每月薪資", "category": "收入", "amount": 62000, "day": 8, "type": "income", "active": True})
        self.assertEqual(item["type"], "expense")
        self.assertEqual(income["type"], "income")
        self.assertTrue(item["active"])
        self.assertTrue(self.db.set_recurring_active(item["id"], False))
        self.assertTrue(any(not row["active"] for row in self.db.list_recurring()))

    def test_pdf_columns_are_persisted(self) -> None:
        transaction = self.db.create_transaction({
            "title": "義美股份有限公司", "category": "其他", "amount": 69,
            "date": "2026-08-10", "type": "expense", "source": "台北富邦 PDF 匯入",
            "transaction_time": "2026/08/10 02:26:23", "summary": "刷卡消費",
            "expense_amount": 69, "income_amount": None, "balance": 465024,
            "note": "義美股份有限公司",
        })
        self.assertEqual(transaction["summary"], "刷卡消費")
        self.assertEqual(transaction["balance"], 465024)
        self.assertEqual(transaction["note"], "義美股份有限公司")
