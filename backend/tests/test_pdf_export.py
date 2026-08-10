from unittest import TestCase

from pypdf import PdfReader

from backend.app.pdf_export import build_financial_analysis_pdf, build_transactions_pdf


class PdfExportTests(TestCase):
    def test_export_creates_readable_pdf(self) -> None:
        content = build_transactions_pdf([{
            "id": 1, "title": "義美股份有限公司", "category": "其他", "amount": 69,
            "date": "2026-08-10", "type": "expense", "source": "PDF 匯入",
            "transaction_time": "2026/08/10 02:26:23", "summary": "刷卡消費",
            "expense_amount": 69, "income_amount": None, "balance": 465024,
            "note": "義美股份有限公司",
        }])
        self.assertTrue(content.startswith(b"%PDF"))
        reader = PdfReader(__import__("io").BytesIO(content))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(reader.metadata.title, "SelfBank 交易紀錄")

    def test_financial_analysis_pdf_includes_fixed_income_and_expense(self) -> None:
        content = build_financial_analysis_pdf(
            [{"title": "薪資", "category": "股票", "amount": 40000, "date": "2026-08-10", "type": "income"},
             {"title": "餐飲", "category": "餐飲", "amount": 1000, "date": "2026-08-10", "type": "expense"}],
            [{"title": "固定收入", "category": "股票", "amount": 5000, "day": 10, "type": "income", "active": True},
             {"title": "房租", "category": "日用品", "amount": 8000, "day": 5, "type": "expense", "active": True}],
        )
        self.assertTrue(content.startswith(b"%PDF"))
        reader = PdfReader(__import__("io").BytesIO(content))
        self.assertGreaterEqual(len(reader.pages), 1)
        self.assertEqual(reader.metadata.title, "SelfBank 財務分析報表")
