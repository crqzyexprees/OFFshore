"""The HTTP adapter: routes map onto the ledger and Statement import, and
import problems reach the UI in the shape src/lib/db.ts expects."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api
from backend.db import connect
from backend.statement_import import PROBLEMS, Document, Page

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(api, "get_connection", lambda: connect(db_path))
    monkeypatch.setattr(api, "MODEL_DIR", tmp_path / "no-model")
    # Uploads carry a stub PDF; each test says which Document it "contains".
    monkeypatch.setattr(api, "read_pdf", lambda path: client.document)
    with TestClient(api.app, base_url="http://127.0.0.1") as client:
        yield client


def upload(client, document, **form):
    client.document = document
    return client.post("/api/import", files={"file": ("s.pdf", b"%PDF-1.4 stub")}, data=form)


def chase(*lines, period=True):
    header = ["Chase Freedom", "Account ending in 1234"]
    if period:
        header.append("Opening/Closing Date 12/05/25 - 01/04/26")
    return Document("s.pdf", [Page("\n".join([*header, *lines]))])


def add_card(client):
    return client.post("/api/accounts", json={"name": "Card", "kind": "credit_card", "bank": "chase", "last_four": "1234"}).json()["id"]


def test_reference_serves_the_vocabulary(client):
    ref = client.get("/api/reference").json()
    assert {"id": "internal_transfer", "name": "Internal Transfer"} in ref["kinds"]
    assert ref["categorized_kinds"] == ["purchase", "refund"]
    assert [k["id"] for k in ref["account_kinds"]] == ["credit_card", "bank"]
    assert "Housing" in ref["categories"]


def test_import_then_spending(client):
    add_card(client)
    result = upload(client, chase("12/10 SHOES 100.00", "12/20 SHOES -40.00", "12/22 ATM CASH ADVANCE 60.00"))
    assert result.status_code == 200, result.text
    assert result.json()["imported"] == 3 and result.json()["period_start"] == "2025-12-05"
    assert client.get("/api/spending/2025-12").json() == {
        "categories": [{"category": "Other", "cents": 6000}],
        "withdrawn_cents": 6000,
    }


def test_import_problems_carry_their_fields(client):
    account_id = add_card(client)
    response = upload(client, chase("12/10 SHOES 100.00", period=False))
    assert response.status_code == 422
    assert response.json()["detail"] == {
        "problem": "needs_period",
        "message": "The billing period isn't printed in a form we recognise. Enter it to continue.",
        "account_id": account_id,
    }

    response = upload(client, chase("12/10 SHOES 100.00", period=False),
                      account_id=account_id, period_start="2025-12-05", period_end="2026-01-04")
    assert response.status_code == 200


def test_override_errors_map_to_http_statuses(client):
    add_card(client)
    upload(client, chase("12/10 SHOES 100.00"))
    [tx] = client.get("/api/transactions").json()
    assert client.post(f"/api/transactions/{tx['id']}/override", json={"kind": "gift"}).status_code == 400
    assert client.post("/api/transactions/999/override", json={"category": "Dining"}).status_code == 404
    assert client.post(f"/api/transactions/{tx['id']}/override", json={"category": "Dining"}).status_code == 200
    assert client.get("/api/transactions").json()[0]["category"] == "Dining"


def test_unknown_account_kind_is_a_bad_request(client):
    response = client.post("/api/accounts", json={"name": "X", "kind": "debit_card", "bank": "chase"})
    assert response.status_code == 400


def test_the_ui_knows_every_import_problem_and_its_fields():
    db_ts = (ROOT / "src" / "lib" / "db.ts").read_text()
    union = db_ts[db_ts.index("export type ImportProblem"):]
    union = union[: union.index(");")]
    members = {
        m[1]: set(re.findall(r"(\w+)\??:", m[2])) - {"problem"}
        for m in re.finditer(r'\{\s*problem:\s*"(\w+)";?([^}]*)\}', union)
    }
    assert members == {p.code: set(p.FIELDS) for p in PROBLEMS}


def test_csv_export_import_and_unreadable_files(client):
    account_id = add_card(client)
    csv = b"Date,Description,Amount\n2025-12-10,SHOES,100.00\n"
    form = {"account_id": account_id, "period_start": "2025-12-05", "period_end": "2026-01-04"}
    response = client.post("/api/import", files={"file": ("card.csv", csv)}, data=form)
    assert response.status_code == 200 and response.json()["imported"] == 1

    response = client.post("/api/import", files={"file": ("card.csv", b"Date,Amount\n")}, data=form)
    assert response.status_code == 400
    response = client.post("/api/import", files={"file": ("notes.txt", b"hi")}, data=form)
    assert response.status_code == 400
