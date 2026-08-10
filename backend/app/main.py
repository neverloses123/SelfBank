from __future__ import annotations

import base64
import binascii
import os
import io
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, SecretStr

from .database import Database
from .pdf_import import PdfPasswordError, parse_statement_pdf
from .pdf_export import build_financial_analysis_pdf, build_transactions_pdf


class TransactionInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    amount: float = Field(ge=0)
    date: str
    type: Literal["expense", "income"]
    source: str = Field(default="手動記帳", max_length=40)
    transaction_time: str | None = None
    summary: str | None = None
    expense_amount: float | None = Field(default=None, ge=0)
    income_amount: float | None = Field(default=None, ge=0)
    balance: float | None = None
    note: str | None = None


class RecurringInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    amount: float = Field(gt=0)
    day: int = Field(ge=1, le=28)
    type: Literal["expense", "income"] = "expense"
    active: bool = True


class TransactionUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    amount: float = Field(ge=0)
    date: str
    type: Literal["expense", "income"]
    note: str | None = Field(default=None, max_length=200)


class PdfImportInput(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=20_000_000)
    password: SecretStr = Field(min_length=1)


database = None
database_error: str | None = None
if os.getenv("SELFBANK_DB_BACKEND", "sqlite").lower() == "sqlserver":
    from .sqlserver_database import SqlServerDatabase

    try:
        database = SqlServerDatabase(
            os.getenv(
                "SELFBANK_SQLSERVER_CONNECTION",
                "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=HomeAccounting;Trusted_Connection=yes;Encrypt=no;TrustServerCertificate=yes;",
            )
        )
    except Exception as error:
        database_error = str(error)
else:
    database = Database(os.getenv("SELFBANK_DB_PATH", str(Path(__file__).parents[1] / "data" / "selfbank.db")))
app = FastAPI(title="SelfBank API", version="1.0.0", docs_url="/docs")

origins = [origin.strip() for origin in os.getenv("SELFBANK_CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Content-Type"])


def require_database():
    if database is None:
        raise HTTPException(status_code=503, detail="SQL Server 未連線")
    return database


@app.get("/health")
def health():
    if database is None:
        return JSONResponse(status_code=503, content={"status": "disconnected", "database": "HomeAccounting", "detail": database_error or "SQL Server 未連線"})
    try:
        result = database.health_check()
        return {"status": "ok", **result}
    except Exception as error:
        return JSONResponse(status_code=503, content={"status": "disconnected", "database": "HomeAccounting", "detail": str(error)})


@app.get("/transactions")
def transactions(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
    return require_database().list_transactions(limit)


@app.get("/categories")
def categories() -> list[dict]:
    return require_database().list_categories()


@app.get("/transaction-types")
def transaction_types() -> list[dict]:
    return require_database().list_transaction_types()


@app.post("/transactions", status_code=201)
def create_transaction(payload: TransactionInput) -> dict:
    return require_database().create_transaction(payload.model_dump())


@app.patch("/transactions/{item_id}")
def update_transaction(item_id: int, payload: TransactionUpdate) -> dict:
    updated = require_database().update_transaction(item_id, payload.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return updated


@app.delete("/transactions/outside-range")
def prune_transactions(from_date: date, to_date: date) -> dict[str, int | str]:
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    deleted = require_database().prune_transactions(from_date.isoformat(), to_date.isoformat())
    return {"deleted_count": deleted, "retained_from": from_date.isoformat(), "retained_to": to_date.isoformat()}


@app.post("/imports/pdf")
def import_pdf(payload: PdfImportInput) -> dict:
    if not payload.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="請選擇 PDF 檔案")
    try:
        pdf_bytes = base64.b64decode(payload.content_base64, validate=True)
        transactions = parse_statement_pdf(pdf_bytes, payload.password.get_secret_value())
        return require_database().import_transactions(transactions)
    except PdfPasswordError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/exports/pdf")
def export_pdf() -> StreamingResponse:
    content = build_transactions_pdf(require_database().list_transactions(limit=10_000))
    return StreamingResponse(
        io.BytesIO(content), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="selfbank-transactions.pdf"'},
    )


@app.get("/exports/analysis-pdf")
def export_analysis_pdf() -> StreamingResponse:
    db = require_database()
    content = build_financial_analysis_pdf(db.list_transactions(limit=10_000), db.list_recurring())
    return StreamingResponse(
        io.BytesIO(content), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="selfbank-financial-analysis.pdf"'},
    )


@app.get("/recurring")
def recurring() -> list[dict]:
    return require_database().list_recurring()


@app.post("/recurring", status_code=201)
def create_recurring(payload: RecurringInput) -> dict:
    return require_database().create_recurring(payload.model_dump())


@app.patch("/recurring/{item_id}")
def update_recurring(item_id: int, active: bool) -> dict[str, bool]:
    if not require_database().set_recurring_active(item_id, active):
        raise HTTPException(status_code=404, detail="Recurring payment not found")
    return {"updated": True}


@app.delete("/recurring/{item_id}")
def delete_recurring(item_id: int) -> dict[str, bool]:
    if not require_database().delete_recurring(item_id):
        raise HTTPException(status_code=404, detail="Recurring payment not found")
    return {"deleted": True}
