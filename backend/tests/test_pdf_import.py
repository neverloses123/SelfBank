import io
from unittest import TestCase

from pypdf import PdfWriter

from backend.app.pdf_import import PdfPasswordError, extract_pdf_text, parse_fubon_tables, parse_statement_text


class PdfImportTests(TestCase):
    def encrypted_pdf(self, password: str) -> bytes:
        output = io.BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=200)
        writer.encrypt(password)
        writer.write(output)
        return output.getvalue()

    def test_encrypted_pdf_requires_correct_password(self) -> None:
        content = self.encrypted_pdf("test-only-password")
        with self.assertRaises(PdfPasswordError):
            extract_pdf_text(content, "wrong-password")
        self.assertEqual(extract_pdf_text(content, "test-only-password"), "")

    def test_parse_common_statement_rows(self) -> None:
        rows = parse_statement_text("2026/08/10 Coffee Shop -120\n2026-08-11 Salary 62,000")
        self.assertEqual(rows[0]["type"], "expense")
        self.assertEqual(rows[0]["amount"], 120)
        self.assertEqual(rows[1]["type"], "income")
        self.assertEqual(rows[1]["amount"], 62000)

    def test_parse_taipei_fubon_table_and_choose_merchant_note(self) -> None:
        table = [[
            ["帳務日期", "交易時間", "摘要", "支出金額", "存入金額", "即時餘額", "附註"],
            ["2026/08/10", "2026/08/10\n02:26:23", "刷卡消費", "69.00", "", "465,024.00", "義美股份有限公司"],
            ["2026/08/10", "2026/08/10\n02:19:47", "刷卡退貨", "", "219.00", "465,128.00", "連加＊ＬＩＮＥ"],
            ["2026/08/07", "2026/08/06\n23:05:14", "ＣＤ轉收", "", "16,000.00", "470,289.00", "********13296416"],
        ]]
        rows = parse_fubon_tables(table)
        self.assertEqual(rows[0]["title"], "義美股份有限公司")
        self.assertEqual(rows[0]["type"], "expense")
        self.assertEqual(rows[0]["amount"], 69)
        self.assertEqual(rows[0]["transaction_time"], "2026/08/10 02:26:23")
        self.assertEqual(rows[0]["summary"], "刷卡消費")
        self.assertEqual(rows[0]["expense_amount"], 69)
        self.assertEqual(rows[0]["balance"], 465024)
        self.assertEqual(rows[0]["note"], "義美股份有限公司")
        self.assertEqual(rows[1]["type"], "income")
        self.assertEqual(rows[1]["amount"], 219)
        self.assertEqual(rows[2]["title"], "ＣＤ轉收")
        self.assertEqual(rows[2]["amount"], 16000)

    def test_parse_continuation_tables_from_later_pdf_pages(self) -> None:
        tables = [
            [
                ["帳務日期", "交易時間", "摘要", "支出金額", "存入金額", "即時餘額", "附註"],
                ["2026/08/10", "2026/08/10 10:00", "刷卡消費", "100.00", "", "9,900.00", "第一頁商店"],
            ],
            [
                ["2026/08/09", "2026/08/09 11:00", "刷卡消費", "200.00", "", "9,700.00", "第二頁商店"],
            ],
            [
                ["2026/08/08", "2026/08/08 12:00", "發票獎金", "", "300.00", "10,000.00", "第三頁資料"],
            ],
        ]
        rows = parse_fubon_tables(tables)
        self.assertEqual(len(rows), 3)
        self.assertEqual([row["title"] for row in rows], ["第一頁商店", "第二頁商店", "發票獎金"])
        self.assertEqual(rows[2]["type"], "income")
