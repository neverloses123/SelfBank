from unittest import TestCase

from pypdf import PdfReader

from backend.app.pdf_export import build_transactions_pdf


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
