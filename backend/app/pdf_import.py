from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

from pypdf import PdfReader


class PdfPasswordError(ValueError):
    """Raised when an encrypted PDF cannot be opened with the supplied password."""


DATE_PATTERN = re.compile(r"^(\d{4}[/-]\d{1,2}[/-]\d{1,2})\s+(.+?)\s+(-?[\d,]+(?:\.\d{1,2})?)$")


def extract_pdf_text(content: bytes, password: str) -> str:
    reader = PdfReader(io.BytesIO(content))
    if reader.is_encrypted:
        if not password or reader.decrypt(password) == 0:
            raise PdfPasswordError("PDF 密碼錯誤，請重新輸入")
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_statement_text(text: str) -> list[dict[str, Any]]:
    """Parse common text-PDF rows: YYYY/MM/DD description amount."""
    transactions: list[dict[str, Any]] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        match = DATE_PATTERN.match(line)
        if not match:
            continue
        raw_date, title, raw_amount = match.groups()
        parsed_date = datetime.strptime(raw_date.replace("-", "/"), "%Y/%m/%d").date().isoformat()
        amount = float(raw_amount.replace(",", ""))
        transactions.append(
            {
                "title": title.strip(),
                "category": "其他",
                "amount": abs(amount),
                "date": parsed_date,
                "type": "expense" if amount < 0 else "income",
                "source": "銀行 PDF 匯入",
            }
        )
    if not transactions:
        raise ValueError("找不到可匯入的交易列；目前支援文字型 PDF 的『日期 名稱 金額』格式")
    return transactions
