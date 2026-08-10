import io
from unittest import TestCase

from pypdf import PdfWriter

from backend.app.pdf_import import PdfPasswordError, extract_pdf_text, parse_statement_text


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
