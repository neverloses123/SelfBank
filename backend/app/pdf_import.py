from __future__ import annotations

import io
import re
from datetime import datetime
from typing import Any

import pdfplumber
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


def _clean_cell(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _amount(value: Any) -> float | None:
    cleaned = _clean_cell(value).replace(",", "").replace("$", "")
    if not cleaned:
        return None
    try:
        return abs(float(cleaned))
    except ValueError:
        return None


def parse_fubon_tables(tables: list[list[list[Any]]]) -> list[dict[str, Any]]:
    """Parse Taipei Fubon TWD demand-deposit statement tables."""
    transactions: list[dict[str, Any]] = []
    for table in tables:
        header_index = next(
            (index for index, row in enumerate(table) if row and "帳務日期" in "".join(_clean_cell(cell) for cell in row)),
            None,
        )
        if header_index is None:
            continue
        header = [_clean_cell(cell) for cell in table[header_index]]
        indexes = {name: next((i for i, cell in enumerate(header) if name in cell), -1) for name in ("帳務日期", "交易時間", "摘要", "支出金額", "存入金額", "即時餘額", "附註")}
        if min(indexes.values()) < 0:
            continue
        for row in table[header_index + 1 :]:
            if not row or len(row) <= max(indexes.values()):
                continue
            raw_date = _clean_cell(row[indexes["帳務日期"]])
            if not re.fullmatch(r"\d{4}/\d{2}/\d{2}", raw_date):
                continue
            summary = _clean_cell(row[indexes["摘要"]])
            note = _clean_cell(row[indexes["附註"]])
            transaction_time = _clean_cell(row[indexes["交易時間"]])
            expense = _amount(row[indexes["支出金額"]])
            income = _amount(row[indexes["存入金額"]])
            balance = _amount(row[indexes["即時餘額"]])
            if expense is None and income is None:
                continue
            is_expense = expense is not None
            title = note if summary in {"刷卡消費", "刷卡退貨"} and note else summary
            transactions.append(
                {
                    "title": title or "未命名交易",
                    "category": "其他",
                    "amount": expense if is_expense else income,
                    "date": datetime.strptime(raw_date, "%Y/%m/%d").date().isoformat(),
                    "type": "expense" if is_expense else "income",
                    "source": "PDF 匯入",
                    "transaction_time": transaction_time,
                    "summary": summary,
                    "expense_amount": expense,
                    "income_amount": income,
                    "balance": balance,
                    "note": note,
                }
            )
    return transactions


def parse_statement_pdf(content: bytes, password: str) -> list[dict[str, Any]]:
    text = extract_pdf_text(content, password)
    with pdfplumber.open(io.BytesIO(content), password=password) as pdf:
        tables = [table for page in pdf.pages for table in page.extract_tables()]
    fubon_rows = parse_fubon_tables(tables)
    return fubon_rows or parse_statement_text(text)


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
        raise ValueError("找不到可匯入的交易列；請確認 PDF 內含可選取的交易明細文字與表格")
    return transactions
