from __future__ import annotations

import base64
import binascii
import os
import io
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, SecretStr

from .database import Database
from .pdf_import import PdfPasswordError, parse_statement_pdf
from .pdf_export import build_transactions_pdf


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


class PdfImportInput(BaseModel):
    filename: str = Field(min_length=1, max_length=200)
    content_base64: str = Field(min_length=1, max_length=20_000_000)
    password: SecretStr = Field(min_length=1)


if os.getenv("SELFBANK_DB_BACKEND", "sqlite").lower() == "sqlserver":
    from .sqlserver_database import SqlServerDatabase

    database = SqlServerDatabase(
        os.getenv(
            "SELFBANK_SQLSERVER_CONNECTION",
            "DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost,1433;DATABASE=SelfBank;Trusted_Connection=yes;TrustServerCertificate=yes;",
        )
    )
else:
    database = Database(os.getenv("SELFBANK_DB_PATH", str(Path(__file__).parents[1] / "data" / "selfbank.db")))
app = FastAPI(title="SelfBank API", version="1.0.0", docs_url="/docs")

origins = [origin.strip() for origin in os.getenv("SELFBANK_CORS_ORIGINS", "http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/transactions")
def transactions(limit: int = Query(default=200, ge=1, le=1000)) -> list[dict]:
    return database.list_transactions(limit)


@app.post("/transactions", status_code=201)
def create_transaction(payload: TransactionInput) -> dict:
    return database.create_transaction(payload.model_dump())


@app.post("/imports/pdf")
def import_pdf(payload: PdfImportInput) -> dict:
    if not payload.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="請選擇 PDF 檔案")
    try:
        pdf_bytes = base64.b64decode(payload.content_base64, validate=True)
        transactions = parse_statement_pdf(pdf_bytes, payload.password.get_secret_value())
        return database.import_transactions(transactions)
    except PdfPasswordError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error
    except (ValueError, binascii.Error) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/exports/pdf")
def export_pdf() -> StreamingResponse:
    content = build_transactions_pdf(database.list_transactions(limit=10_000))
    return StreamingResponse(
        io.BytesIO(content), media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="selfbank-transactions.pdf"'},
    )


@app.get("/recurring")
def recurring() -> list[dict]:
    return database.list_recurring()


@app.post("/recurring", status_code=201)
def create_recurring(payload: RecurringInput) -> dict:
    return database.create_recurring(payload.model_dump())


@app.patch("/recurring/{item_id}")
def update_recurring(item_id: int, active: bool) -> dict[str, bool]:
    if not database.set_recurring_active(item_id, active):
        raise HTTPException(status_code=404, detail="Recurring payment not found")
    return {"updated": True}
