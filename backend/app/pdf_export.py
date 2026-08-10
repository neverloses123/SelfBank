from __future__ import annotations

import io
from pathlib import Path
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT_NAME = "SelfBankTC"
WINDOWS_FONT = Path("C:/Windows/Fonts/msjh.ttc")
if WINDOWS_FONT.exists():
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(WINDOWS_FONT), subfontIndex=0))
else:
    FONT_NAME = "MSung-Light"
    pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))


def _money(value: Any) -> str:
    if value is None:
        return "-"
    return f"{float(value):,.2f}"


def _text(value: Any) -> str:
    return str(value or "-").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_transactions_pdf(transactions: list[dict[str, Any]]) -> bytes:
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=landscape(A4), leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=11 * mm, bottomMargin=11 * mm, title="SelfBank 交易紀錄",
        author="SelfBank",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleTC", parent=styles["Title"], fontName=FONT_NAME, fontSize=18, leading=24, textColor=colors.HexColor("#1f6b4f"))
    meta_style = ParagraphStyle("MetaTC", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8, leading=11, alignment=TA_CENTER, textColor=colors.HexColor("#6f7d75"))
    cell_style = ParagraphStyle("CellTC", parent=styles["Normal"], fontName=FONT_NAME, fontSize=7.2, leading=9)
    header_style = ParagraphStyle("HeaderTC", parent=cell_style, textColor=colors.white, alignment=TA_CENTER)

    headers = ["帳務日期", "交易時間", "摘要", "支出金額", "存入金額", "即時餘額", "附註"]
    rows = [[Paragraph(header, header_style) for header in headers]]
    for item in transactions:
        summary = item.get("summary") or item.get("title")
        expense = item.get("expense_amount") if item.get("type") == "expense" else None
        income = item.get("income_amount") if item.get("type") == "income" else None
        if expense is None and item.get("type") == "expense":
            expense = item.get("amount")
        if income is None and item.get("type") == "income":
            income = item.get("amount")
        note = item.get("note") or (item.get("title") if item.get("summary") else "-")
        rows.append([
            Paragraph(_text(item.get("date")), cell_style),
            Paragraph(_text(item.get("transaction_time")), cell_style),
            Paragraph(_text(summary), cell_style),
            Paragraph(_money(expense), cell_style),
            Paragraph(_money(income), cell_style),
            Paragraph(_money(item.get("balance")), cell_style),
            Paragraph(_text(note), cell_style),
        ])

    if len(rows) == 1:
        rows.append([Paragraph("目前沒有交易紀錄", cell_style), "", "", "", "", "", ""])

    table = Table(rows, repeatRows=1, colWidths=[24 * mm, 39 * mm, 35 * mm, 27 * mm, 27 * mm, 29 * mm, 76 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6b4f")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfdad4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (3, 1), (5, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6faf7")]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story = [
        Paragraph("SelfBank 交易紀錄", title_style),
        Paragraph(f"匯出時間：{datetime.now().strftime('%Y/%m/%d %H:%M')}　共 {len(transactions)} 筆", meta_style),
        Spacer(1, 5 * mm), table,
    ]
    doc.build(story)
    return output.getvalue()
