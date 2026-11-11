import hmac
import os
import tempfile
from contextlib import asynccontextmanager, closing
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from backend import backup, ledger, prediction
from backend.config import BACKUP_DIR, MODEL_DIR, SAFETY_DIR
from backend.db import get_connection, init_db
from backend.statement_import import BANKS, ImportProblem, import_statement, is_export, read_export, read_pdf
from backend.vocabulary import ACCOUNT_KINDS, CATEGORIES, CATEGORIZED_KINDS, KINDS

predictor: prediction.CategoryPredictor = prediction.NoModel()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global predictor
    with closing(get_connection()) as conn:
        init_db(conn)
    predictor = prediction.load(MODEL_DIR, corrections=_corrections)
    yield


def _corrections() -> list[tuple[str, str]]:
    """The user's hand-set Categories, which the example predictor learns from."""
    with closing(get_connection()) as conn:
        return [(c["description"], c["category"]) for c in ledger.corrections(conn)]


app = FastAPI(title="SplitLens API", lifespan=lifespan)

# Set by `python -m backend --sidecar`: the Tauri shell launches the backend on a
# random port and hands this per-launch token to the UI. In browser dev mode
# (no token) the UI is same-origin through the Vite proxy, so CORS stays off.
API_TOKEN = os.environ.get("SPLITLENS_API_TOKEN")

if API_TOKEN:

    @app.middleware("http")
    async def require_token(request: Request, call_next):
        auth = request.headers.get("authorization", "")
        if not hmac.compare_digest(auth, f"Bearer {API_TOKEN}"):
            return JSONResponse({"detail": "Unauthorized"}, status_code=401)
        return await call_next(request)

    # Added after the token check so it wraps it: CORS preflights (which carry
    # no token) are answered before the check runs.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["tauri://localhost", "http://tauri.localhost", "http://localhost:1420"],
        allow_methods=["*"],
        allow_headers=["authorization", "content-type"],
    )

# Rejecting foreign Host headers blocks DNS-rebinding attacks.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])


class AccountIn(BaseModel):
    name: str = Field(min_length=1)
    kind: str
    bank: str
    last_four: Optional[str] = Field(default=None, pattern=r"^\d{4}$")
    color: str = "#6366f1"


class BackupIn(BaseModel):
    """No password: a plain copy. A password: an encrypted Backup."""

    password: Optional[str] = None


class BudgetIn(BaseModel):
    """A Category's Budget from a month on; null removes it."""

    category: str
    amount_cents: Optional[int] = None


class OverrideIn(BaseModel):
    """Set or clear (null) the Override for a Transaction's kind and Category."""

    kind: Optional[str] = None
    category: Optional[str] = None


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": not isinstance(predictor, prediction.NoModel)}


@app.get("/api/reference")
def reference():
    """The vocabularies the UI offers, as the backend defines them."""
    return {
        "banks": [{"id": k, "name": v} for k, v in BANKS.items()],
        "kinds": [{"id": k, "name": v} for k, v in KINDS.items()],
        "categorized_kinds": list(CATEGORIZED_KINDS),
        "account_kinds": [{"id": k, "name": v} for k, v in ACCOUNT_KINDS.items()],
        "categories": list(CATEGORIES),
    }


def _refused(e: ledger.LedgerError) -> HTTPException:
    return HTTPException(status_code=404 if isinstance(e, ledger.NotFound) else 400, detail=str(e))


@app.get("/api/accounts")
def get_accounts():
    with closing(get_connection()) as conn:
        return ledger.accounts(conn)


@app.post("/api/accounts")
def add_account(account: AccountIn):
    if account.bank not in BANKS:
        raise HTTPException(status_code=400, detail=f"Unknown bank: {account.bank}")
    with closing(get_connection()) as conn:
        try:
            return {"id": ledger.add_account(conn, **account.model_dump())}
        except ledger.LedgerError as e:
            raise _refused(e) from e


@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: int):
    with closing(get_connection()) as conn:
        ledger.delete_account(conn, account_id)
    return {"ok": True}


@app.get("/api/transactions")
def get_transactions(
    account_id: Optional[int] = None,
    month: Optional[str] = None,
    category: Optional[str] = None,
    kind: Optional[str] = None,
):
    with closing(get_connection()) as conn:
        return ledger.transactions(conn, ledger.TransactionFilter(account_id, month, category, kind))


@app.get("/api/spending/{month}")
def get_spending(month: str):
    """Spending (Purchases minus Refunds) per Category, plus cash withdrawn."""
    with closing(get_connection()) as conn:
        result = ledger.spending(conn, month)
    return {
        "categories": [{"category": c, "cents": cents} for c, cents in result.by_category.items()],
        "withdrawn_cents": result.withdrawn_cents,
    }


@app.get("/api/budgets/{month}")
def get_budgets(month: str):
    """Every Category with a Budget or Spending this month."""
    with closing(get_connection()) as conn:
        try:
            budgets = ledger.budgets(conn, month)
        except ledger.LedgerError as e:
            raise _refused(e) from e
        spent = ledger.spending(conn, month).by_category
    names = sorted(set(budgets) | set(spent), key=lambda c: (c not in budgets, -spent.get(c, 0), c))
    return {
        "categories": [
            {"category": c, "budget_cents": budgets.get(c), "spent_cents": spent.get(c, 0)} for c in names
        ],
    }


@app.put("/api/budgets/{month}")
def put_budget(month: str, body: BudgetIn):
    with closing(get_connection()) as conn:
        try:
            ledger.set_budget(conn, body.category, month, body.amount_cents)
        except ledger.LedgerError as e:
            raise _refused(e) from e
    return {"ok": True}


@app.post("/api/transactions/{tx_id}/override")
def set_override(tx_id: int, body: OverrideIn):
    with closing(get_connection()) as conn:
        try:
            ledger.set_override(conn, tx_id, kind=body.kind, category=body.category, predictor=predictor)
        except ledger.LedgerError as e:
            raise _refused(e) from e
        # A predictor that learns from corrections can now do better elsewhere.
        updated = ledger.repredict(conn, predictor) if isinstance(predictor, prediction.ExamplePredictor) else 0
    return {"ok": True, "repredicted": updated}


@app.post("/api/import")
def import_statement_route(
    file: UploadFile = File(...),
    account_id: Optional[int] = Form(None),
    period_start: Optional[date] = Form(None),
    period_end: Optional[date] = Form(None),
):
    file_name = Path(file.filename or "statement.pdf").name
    data = file.file.read()
    if (period_start is None) != (period_end is None):
        raise HTTPException(status_code=400, detail="Give both ends of the billing period")
    period = (period_start, period_end) if period_start and period_end else None

    if is_export(file_name):
        try:
            document = read_export(data, file_name)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    elif Path(file_name).suffix.lower() == ".pdf" and data.startswith(b"%PDF"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / file_name
            path.write_bytes(data)
            document = read_pdf(path)
    else:
        raise HTTPException(status_code=400, detail="The file is not a PDF, CSV, OFX or QFX file")

    with closing(get_connection()) as conn:
        try:
            result = import_statement(conn, document, account_id=account_id, period=period, predictor=predictor)
        except ImportProblem as e:
            raise HTTPException(status_code=422, detail=e.to_json()) from e
    return result.to_json()


@app.get("/api/backups")
def backup_location():
    return {"directory": str(BACKUP_DIR), "min_password": backup.MIN_PASSWORD}


@app.post("/api/backups")
def save_backup(body: BackupIn):
    with closing(get_connection()) as conn:
        try:
            saved = backup.save_backup(conn, BACKUP_DIR, body.password or None)
        except backup.BackupError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"path": str(saved.path), "encrypted": saved.encrypted, "size": saved.size}


@app.post("/api/restore")
def restore_backup(file: UploadFile = File(...), password: Optional[str] = Form(None)):
    data = file.file.read()
    with closing(get_connection()) as conn:
        try:
            safety = backup.restore_backup(conn, data, SAFETY_DIR, password or None)
        except backup.BackupError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "previous": str(safety)}
