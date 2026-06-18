from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.classifier import TxClassifier
from backend.config import HOST, MODEL_DIR, PORT
from backend.db import get_connection, init_db
from backend.services import import_pdf

classifier: Optional[TxClassifier] = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global classifier
    conn = get_connection()
    init_db(conn)
    conn.close()

    if (MODEL_DIR / "classifier.onnx").exists():
        try:
            classifier = TxClassifier(MODEL_DIR)
            print(f"Loaded classifier from {MODEL_DIR}")
        except Exception as e:
            print(f"Warning: could not load classifier: {e}")
            classifier = None
    else:
        print(f"No model at {MODEL_DIR / 'classifier.onnx'} — using 'Other' for imports")

    yield


app = FastAPI(title="Finance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AccountIn(BaseModel):
    name: str
    bank: str
    last_four: Optional[str] = None
    color: Optional[str] = "#6366f1"


class ImportIn(BaseModel):
    pdf_path: str
    account_id: int


class CategoryOverride(BaseModel):
    category: str


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": classifier is not None}


@app.get("/api/accounts")
def get_accounts():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, bank, last_four, color FROM accounts ORDER BY name"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.post("/api/accounts")
def add_account(account: AccountIn):
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO accounts (name, bank, last_four, color) VALUES (?, ?, ?, ?)",
            (account.name, account.bank, account.last_four, account.color),
        )
        conn.commit()
        return {"id": cur.lastrowid}
    finally:
        conn.close()


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    conn = get_connection()
    try:
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.get("/api/transactions")
def get_transactions(
    account_id: Optional[int] = None,
    month: Optional[str] = None,
    category: Optional[str] = None,
):
    conn = get_connection()
    try:
        query = """SELECT id, account_id, date, description, merchant, amount, tx_type,
                          category, category_confidence, manually_overridden, manual_category
                   FROM transactions WHERE tx_type = 'debit'"""
        params: list = []

        if account_id is not None:
            params.append(account_id)
            query += f" AND account_id = ?{len(params)}"
        if month:
            params.append(month)
            query += f" AND strftime('%Y-%m', date) = ?{len(params)}"
        if category:
            params.append(category)
            n = len(params)
            query += f" AND (category = ?{n} OR manual_category = ?{n})"

        query += " ORDER BY date DESC"
        rows = conn.execute(query, params).fetchall()
        return [
            {
                **dict(r),
                "manually_overridden": bool(r["manually_overridden"]),
            }
            for r in rows
        ]
    finally:
        conn.close()


@app.get("/api/spending/{month}")
def get_spending_by_category(month: str):
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT COALESCE(manual_category, category, 'Other') as cat,
                      SUM(amount) as total
               FROM transactions
               WHERE tx_type = 'debit' AND strftime('%Y-%m', date) = ?
               GROUP BY cat ORDER BY total DESC""",
            (month,),
        ).fetchall()
        return [[r["cat"], r["total"]] for r in rows]
    finally:
        conn.close()


@app.post("/api/transactions/{tx_id}/category")
def override_category(tx_id: int, body: CategoryOverride):
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE transactions SET manual_category = ?, manually_overridden = 1 WHERE id = ?",
            (body.category, tx_id),
        )
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


@app.post("/api/import")
def import_statement(body: ImportIn):
    path = Path(body.pdf_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {body.pdf_path}")
    if path.suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        result = import_pdf(str(path), body.account_id, classifier)
        return {
            "imported": result.imported,
            "duplicates": result.duplicates,
            "failed": result.failed,
            "bank": result.bank,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
