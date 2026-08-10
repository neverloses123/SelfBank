from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .database import Database


class TransactionInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    amount: float = Field(ge=0)
    date: str
    type: Literal["expense", "income"]
    source: str = Field(default="手動記帳", max_length=40)


class RecurringInput(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    category: str = Field(min_length=1, max_length=40)
    amount: float = Field(gt=0)
    day: int = Field(ge=1, le=28)
    active: bool = True


class CsvImportInput(BaseModel):
    content: str = Field(min_length=1, max_length=5_000_000)


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


@app.post("/imports/csv")
def import_csv(payload: CsvImportInput) -> dict:
    try:
        return database.import_csv(payload.content)
    except (ValueError, KeyError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


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
