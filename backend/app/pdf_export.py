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

    headers = ["類型", "名稱", "金額", "日期", "分類"]
    rows = [[Paragraph(header, header_style) for header in headers]]
    for item in transactions:
        rows.append([
            Paragraph("收入" if item.get("type") == "income" else "支出", cell_style),
            Paragraph(_text(item.get("title")), cell_style),
            Paragraph(("+" if item.get("type") == "income" else "-") + _money(item.get("amount")), cell_style),
            Paragraph(_text(item.get("date")), cell_style),
            Paragraph(_text(item.get("category")), cell_style),
        ])

    if len(rows) == 1:
        rows.append([Paragraph("目前沒有交易紀錄", cell_style), "", "", "", ""])

    table = Table(rows, repeatRows=1, colWidths=[30 * mm, 80 * mm, 45 * mm, 45 * mm, 50 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f6b4f")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#cfdad4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 1), (2, -1), "RIGHT"),
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


def build_financial_analysis_pdf(transactions: list[dict[str, Any]], recurring: list[dict[str, Any]]) -> bytes:
    now = datetime.now()
    month_key = now.strftime("%Y-%m")
    monthly = [item for item in transactions if str(item.get("date", "")).startswith(month_key)]
    active_recurring = [item for item in recurring if item.get("active")]
    actual_income = sum(float(item.get("amount", 0)) for item in monthly if item.get("type") == "income")
    actual_expense = sum(float(item.get("amount", 0)) for item in monthly if item.get("type") == "expense")
    fixed_income = sum(float(item.get("amount", 0)) for item in active_recurring if item.get("type") == "income")
    fixed_expense = sum(float(item.get("amount", 0)) for item in active_recurring if item.get("type") == "expense")
    projected_income = actual_income + fixed_income
    projected_expense = actual_expense + fixed_expense
    projected_balance = projected_income - projected_expense
    savings_rate = max(0, projected_balance / projected_income * 100) if projected_income else 0

    categories: dict[str, float] = {}
    for item in monthly:
        if item.get("type") == "expense":
            category = str(item.get("category") or "未分類")
            categories[category] = categories.get(category, 0) + float(item.get("amount", 0))

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm, title="SelfBank 財務分析報表", author="SelfBank",
    )
    styles = getSampleStyleSheet()
    process_blue = colors.HexColor("#0085CA")
    pale_blue = colors.HexColor("#E6F4FA")
    title_style = ParagraphStyle("AnalysisTitleTC", parent=styles["Title"], fontName=FONT_NAME, fontSize=20, leading=26, textColor=process_blue)
    heading_style = ParagraphStyle("AnalysisHeadingTC", parent=styles["Heading2"], fontName=FONT_NAME, fontSize=13, leading=18, textColor=process_blue, spaceBefore=5 * mm, spaceAfter=2 * mm)
    body_style = ParagraphStyle("AnalysisBodyTC", parent=styles["Normal"], fontName=FONT_NAME, fontSize=8.5, leading=12)
    header_style = ParagraphStyle("AnalysisHeaderTC", parent=body_style, textColor=colors.white, alignment=TA_CENTER)
    meta_style = ParagraphStyle("AnalysisMetaTC", parent=body_style, alignment=TA_CENTER, textColor=colors.HexColor("#667985"))

    def styled_table(rows: list[list[Any]], widths: list[float]) -> Table:
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), process_blue),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8D9EA")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, pale_blue]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return table

    summary_rows = [[Paragraph(value, header_style) for value in ["項目", "實際交易", "固定收支", "預估合計"]]]
    summary_rows += [
        [Paragraph("收入", body_style), _money(actual_income), _money(fixed_income), _money(projected_income)],
        [Paragraph("支出", body_style), _money(actual_expense), _money(fixed_expense), _money(projected_expense)],
        [Paragraph("盈虧", body_style), _money(actual_income - actual_expense), _money(fixed_income - fixed_expense), _money(projected_balance)],
    ]

    category_rows = [[Paragraph(value, header_style) for value in ["支出分類", "實際金額", "占實際支出"]]]
    for category, amount in sorted(categories.items(), key=lambda row: row[1], reverse=True):
        percentage = amount / actual_expense * 100 if actual_expense else 0
        category_rows.append([Paragraph(_text(category), body_style), _money(amount), f"{percentage:.1f}%"])
    if len(category_rows) == 1:
        category_rows.append([Paragraph("本月沒有實際支出", body_style), "-", "-"])

    recurring_rows = [[Paragraph(value, header_style) for value in ["固定項目", "類型", "金額", "每月日期"]]]
    for item in active_recurring:
        recurring_rows.append([
            Paragraph(_text(item.get("title")), body_style),
            Paragraph("固定收入" if item.get("type") == "income" else "固定支出", body_style),
            _money(item.get("amount")),
            f"{item.get('day', '-')} 日",
        ])
    if len(recurring_rows) == 1:
        recurring_rows.append([Paragraph("目前沒有啟用中的固定收支", body_style), "-", "-", "-"])

    story = [
        Paragraph("SelfBank 財務分析報表", title_style),
        Paragraph(f"分析月份：{now.strftime('%Y 年 %m 月')}　匯出時間：{now.strftime('%Y/%m/%d %H:%M')}", meta_style),
        Spacer(1, 5 * mm),
        Paragraph("本月預估摘要", heading_style),
        styled_table(summary_rows, [43 * mm, 43 * mm, 43 * mm, 43 * mm]),
        Spacer(1, 3 * mm),
        Paragraph(f"預估儲蓄率：{savings_rate:.1f}%（固定收支屬預估值，會與實際交易分開列示）", body_style),
        Paragraph("實際支出分類", heading_style),
        styled_table(category_rows, [75 * mm, 50 * mm, 47 * mm]),
        Paragraph("啟用中的固定收支", heading_style),
        styled_table(recurring_rows, [70 * mm, 38 * mm, 38 * mm, 26 * mm]),
    ]
    doc.build(story)
    return output.getvalue()
