"""Sharing: People, Groups, Shared Expenses, Links, Settlements and Balances.

How a Shared Expense counts as Spending is decided once, in the
`spending_items` view (db.py, docs/adr/0007); this module only records what
was shared and with whom. Balances are always derived, never stored.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from backend.ledger import LedgerError, NotFound
from backend.vocabulary import CATEGORIES

DIRECTIONS = ("to_them", "from_them")  # Settlement: user paid them / they paid the user


def _commit(conn: sqlite3.Connection, sql: str, params=()) -> sqlite3.Cursor:
    try:
        cur = conn.execute(sql, params)
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise LedgerError(_integrity_message(e)) from e
    conn.commit()
    return cur


def _integrity_message(e: sqlite3.IntegrityError) -> str:
    text = str(e)
    if "UNIQUE constraint failed: people.name" in text:
        return "Someone with that name is already in People."
    if "UNIQUE constraint failed: groups.name" in text:
        return "A Group with that name already exists."
    if "FOREIGN KEY constraint failed" in text:
        return "That's still used by Shared Expenses or Settlements."
    return text


def _check_date(text: str) -> None:
    try:
        date.fromisoformat(text)
    except (TypeError, ValueError):
        raise LedgerError(f"Not a date (YYYY-MM-DD): {text}") from None


# ── People ──────────────────────────────────────────────────────────────────

def people(conn: sqlite3.Connection) -> list[dict]:
    """Everyone, with their Balance (positive: they owe the user)."""
    owed = balances(conn)
    rows = conn.execute("SELECT id, name, note FROM people ORDER BY name COLLATE NOCASE")
    return [{**dict(r), "balance_cents": owed.get(r["id"], 0)} for r in rows]


def add_person(conn: sqlite3.Connection, name: str, note: str | None = None) -> int:
    return _commit(conn, "INSERT INTO people (name, note) VALUES (?, ?)", (name.strip(), note or None)).lastrowid


def person_named(conn: sqlite3.Connection, name: str) -> int:
    """The Person with this name, added if they're new."""
    row = conn.execute("SELECT id FROM people WHERE name = ? COLLATE NOCASE", (name.strip(),)).fetchone()
    return row["id"] if row else add_person(conn, name)


def delete_person(conn: sqlite3.Connection, person_id: int) -> None:
    """Refused while any Shared Expense or Settlement involves them."""
    if _commit(conn, "DELETE FROM people WHERE id = ?", (person_id,)).rowcount == 0:
        raise NotFound("Person not found")


# ── Groups ──────────────────────────────────────────────────────────────────

def groups(conn: sqlite3.Connection) -> list[dict]:
    members: dict[int, list[dict]] = {}
    for r in conn.execute(
        """SELECT m.group_id, p.id, p.name FROM group_members m JOIN people p ON p.id = m.person_id
           ORDER BY p.name COLLATE NOCASE"""
    ):
        members.setdefault(r["group_id"], []).append({"id": r["id"], "name": r["name"]})
    return [
        {"id": r["id"], "name": r["name"], "members": members.get(r["id"], [])}
        for r in conn.execute("SELECT id, name FROM groups ORDER BY name COLLATE NOCASE")
    ]


def add_group(conn: sqlite3.Connection, name: str, member_ids: list[int] = ()) -> int:
    group_id = _commit(conn, "INSERT INTO groups (name) VALUES (?)", (name.strip(),)).lastrowid
    for person_id in member_ids:
        add_member(conn, group_id, person_id)
    return group_id


def group_named(conn: sqlite3.Connection, name: str) -> int:
    row = conn.execute("SELECT id FROM groups WHERE name = ? COLLATE NOCASE", (name.strip(),)).fetchone()
    return row["id"] if row else add_group(conn, name)


def add_member(conn: sqlite3.Connection, group_id: int, person_id: int) -> None:
    _commit(conn, "INSERT OR IGNORE INTO group_members (group_id, person_id) VALUES (?, ?)", (group_id, person_id))


def remove_member(conn: sqlite3.Connection, group_id: int, person_id: int) -> None:
    _commit(conn, "DELETE FROM group_members WHERE group_id = ? AND person_id = ?", (group_id, person_id))


def delete_group(conn: sqlite3.Connection, group_id: int) -> None:
    """Its Shared Expenses stay; they just no longer belong to a Group."""
    if _commit(conn, "DELETE FROM groups WHERE id = ?", (group_id,)).rowcount == 0:
        raise NotFound("Group not found")


# ── Shared Expenses ─────────────────────────────────────────────────────────

@dataclass
class NewExpense:
    """A Shared Expense to record. `paid_by` None means the user paid; then
    `shares` holds what each other Person owes, and with the user's Share it
    must add up to the total."""

    date: str
    description: str
    category: str
    total_cents: int
    your_share_cents: int
    paid_by: int | None = None
    shares: dict[int, int] = field(default_factory=dict)
    group_id: int | None = None
    transaction_id: int | None = None
    standalone: bool = False
    source_key: str | None = None


def add_expense(conn: sqlite3.Connection, e: NewExpense, *, commit: bool = True) -> int:
    _check_date(e.date)
    if not e.description.strip():
        raise LedgerError("Describe the expense.")
    if e.category not in CATEGORIES:
        raise LedgerError(f"Unknown Category: {e.category}")
    if e.total_cents <= 0 or e.your_share_cents < 0 or e.your_share_cents > e.total_cents:
        raise LedgerError("Your share must be between zero and the total.")
    shares = {p: c for p, c in e.shares.items() if c}
    if any(c < 0 for c in shares.values()):
        raise LedgerError("A share can't be negative.")
    if e.paid_by is None:
        if not shares:
            raise LedgerError("Choose who you split it with.")
        if e.your_share_cents + sum(shares.values()) != e.total_cents:
            raise LedgerError("The shares must add up to the total.")
    else:
        if shares:
            raise LedgerError("Only record others' shares for expenses you paid.")
        if e.transaction_id is not None or e.standalone:
            raise LedgerError("Only an expense you paid can be linked to your Purchase.")
    if e.transaction_id is not None:
        _check_linkable(conn, e.transaction_id)

    try:
        expense_id = conn.execute(
            """INSERT INTO shared_expenses (date, description, category, total_cents, your_share_cents,
                                            paid_by, group_id, transaction_id, standalone, source_key)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (e.date, e.description.strip(), e.category, e.total_cents, e.your_share_cents,
             e.paid_by, e.group_id, e.transaction_id, int(e.standalone), e.source_key),
        ).lastrowid
        conn.executemany(
            "INSERT INTO shares (expense_id, person_id, cents) VALUES (?, ?, ?)",
            [(expense_id, person_id, cents) for person_id, cents in shares.items()],
        )
    except sqlite3.IntegrityError as err:
        conn.rollback()
        raise LedgerError(_integrity_message(err)) from err
    if commit:
        conn.commit()
    return expense_id


def expenses(conn: sqlite3.Connection, month: str | None = None) -> list[dict]:
    """Shared Expenses, newest first, with who paid, everyone's Shares, the
    Linked Transaction and whether the user's Share counts as Spending yet."""
    where, params = ("WHERE strftime('%Y-%m', e.date) = ?", (month,)) if month else ("", ())
    rows = conn.execute(
        f"""SELECT e.*, p.name AS paid_by_name, g.name AS group_name,
                   t.date AS tx_date, t.description AS tx_description, t.amount_cents AS tx_amount_cents
            FROM shared_expenses e
            LEFT JOIN people p ON p.id = e.paid_by
            LEFT JOIN groups g ON g.id = e.group_id
            LEFT JOIN transactions t ON t.id = e.transaction_id
            {where} ORDER BY e.date DESC, e.id DESC""",
        params,
    ).fetchall()
    shares: dict[int, list[dict]] = {}
    for r in conn.execute(
        "SELECT s.expense_id, s.person_id, p.name, s.cents FROM shares s JOIN people p ON p.id = s.person_id"
    ):
        shares.setdefault(r["expense_id"], []).append({"person_id": r["person_id"], "name": r["name"], "cents": r["cents"]})
    result = []
    for r in rows:
        linked = r["transaction_id"] is not None
        result.append({
            "id": r["id"], "date": r["date"], "description": r["description"], "category": r["category"],
            "total_cents": r["total_cents"], "your_share_cents": r["your_share_cents"],
            "paid_by": r["paid_by"], "paid_by_name": r["paid_by_name"],
            "group_id": r["group_id"], "group_name": r["group_name"],
            "standalone": bool(r["standalone"]),
            "from_splitwise": (r["source_key"] or "").startswith("splitwise:"),
            "shares": sorted(shares.get(r["id"], []), key=lambda s: s["name"].lower()),
            "transaction": {"id": r["transaction_id"], "date": r["tx_date"], "description": r["tx_description"],
                            "amount_cents": r["tx_amount_cents"]} if linked else None,
            "counted": r["paid_by"] is not None or linked or bool(r["standalone"]),
        })
    return result


def delete_expense(conn: sqlite3.Connection, expense_id: int) -> None:
    if _commit(conn, "DELETE FROM shared_expenses WHERE id = ?", (expense_id,)).rowcount == 0:
        raise NotFound("Shared Expense not found")


def _check_linkable(conn: sqlite3.Connection, transaction_id: int) -> None:
    tx = conn.execute(
        "SELECT effective_kind FROM transaction_view WHERE id = ?", (transaction_id,)
    ).fetchone()
    if tx is None:
        raise NotFound("Transaction not found")
    if tx["effective_kind"] != "purchase":
        raise LedgerError("Only a Purchase can be linked to a Shared Expense.")
    if conn.execute("SELECT 1 FROM shared_expenses WHERE transaction_id = ?", (transaction_id,)).fetchone():
        raise LedgerError("That Purchase is already linked to another Shared Expense.")


def _expense(conn, expense_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM shared_expenses WHERE id = ?", (expense_id,)).fetchone()
    if row is None:
        raise NotFound("Shared Expense not found")
    return row


def link(conn: sqlite3.Connection, expense_id: int, transaction_id: int) -> None:
    """Links a Shared Expense the user paid to the Purchase that paid for it."""
    if _expense(conn, expense_id)["paid_by"] is not None:
        raise LedgerError("Only an expense you paid can be linked to your Purchase.")
    _check_linkable(conn, transaction_id)
    _commit(conn, "UPDATE shared_expenses SET transaction_id = ?, standalone = 0 WHERE id = ?",
            (transaction_id, expense_id))


def unlink(conn: sqlite3.Connection, expense_id: int) -> None:
    _expense(conn, expense_id)
    _commit(conn, "UPDATE shared_expenses SET transaction_id = NULL WHERE id = ?", (expense_id,))


def set_standalone(conn: sqlite3.Connection, expense_id: int, standalone: bool) -> None:
    """Marks an expense the user paid as paid outside the tracked Accounts, so
    the user's Share counts without a Linked Purchase."""
    e = _expense(conn, expense_id)
    if e["paid_by"] is not None:
        raise LedgerError("Only an expense you paid can be marked as paid outside your accounts.")
    if standalone and e["transaction_id"] is not None:
        raise LedgerError("Unlink it from its Purchase first.")
    _commit(conn, "UPDATE shared_expenses SET standalone = ? WHERE id = ?", (int(standalone), expense_id))


# ── Settlements and Balances ────────────────────────────────────────────────

def add_settlement(
    conn: sqlite3.Connection, *, date: str, person_id: int, cents: int, direction: str,
    note: str | None = None, source_key: str | None = None, commit: bool = True,
) -> int:
    _check_date(date)
    if direction not in DIRECTIONS:
        raise LedgerError(f"Unknown direction: {direction}")
    if cents <= 0:
        raise LedgerError("A Settlement must be more than zero.")
    try:
        settlement_id = conn.execute(
            "INSERT INTO settlements (date, person_id, cents, direction, note, source_key) VALUES (?, ?, ?, ?, ?, ?)",
            (date, person_id, cents, direction, note, source_key),
        ).lastrowid
    except sqlite3.IntegrityError as e:
        conn.rollback()
        raise LedgerError(_integrity_message(e)) from e
    if commit:
        conn.commit()
    return settlement_id


def settle_up(conn: sqlite3.Connection, person_id: int, on: str) -> int | None:
    """Records the Settlement that brings a Person's Balance to zero."""
    balance = balances(conn).get(person_id, 0)
    if balance == 0:
        return None
    return add_settlement(conn, date=on, person_id=person_id, cents=abs(balance),
                          direction="from_them" if balance > 0 else "to_them", note="Settled up")


def settlements(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT s.id, s.date, s.person_id, p.name, s.cents, s.direction, s.note
           FROM settlements s JOIN people p ON p.id = s.person_id ORDER BY s.date DESC, s.id DESC"""
    )
    return [dict(r) for r in rows]


def delete_settlement(conn: sqlite3.Connection, settlement_id: int) -> None:
    if _commit(conn, "DELETE FROM settlements WHERE id = ?", (settlement_id,)).rowcount == 0:
        raise NotFound("Settlement not found")


def balances(conn: sqlite3.Connection) -> dict[int, int]:
    """Each Person's Balance in cents: positive when they owe the user."""
    rows = conn.execute(
        """SELECT person_id, SUM(cents) AS cents FROM (
               SELECT person_id, cents FROM shares
               UNION ALL SELECT paid_by, -your_share_cents FROM shared_expenses WHERE paid_by IS NOT NULL
               UNION ALL SELECT person_id, CASE direction WHEN 'from_them' THEN -cents ELSE cents END
                         FROM settlements
           ) GROUP BY person_id"""
    )
    return {r["person_id"]: r["cents"] for r in rows if r["cents"]}


# ── Reconcile: suggested Links ──────────────────────────────────────────────

_MIN_SCORE = 60


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", text.lower()) if len(t) > 2}


def _score(tx: sqlite3.Row, e: sqlite3.Row) -> tuple[int, str]:
    """How likely a Purchase paid for a Shared Expense: amount, then date, then words."""
    gap = abs(tx["amount_cents"] - e["total_cents"])
    if gap <= 2:
        score, reasons = 50, ["exact amount"]
    elif gap <= 100:
        score, reasons = 30, ["close amount"]
    else:
        return 0, ""
    days = abs((date.fromisoformat(tx["date"]) - date.fromisoformat(e["date"])).days)
    if days <= 1:
        score, reasons = score + 35, reasons + ["same day"]
    elif days <= 3:
        score, reasons = score + 25, reasons + ["within 3 days"]
    elif days <= 7:
        score, reasons = score + 10, reasons + ["within a week"]
    else:
        return 0, ""
    words = _tokens(e["description"])
    overlap = len(words & _tokens(tx["description"])) / len(words) if words else 0
    if overlap >= 0.5:
        score, reasons = score + 15, reasons + ["description matches"]
    elif overlap > 0:
        score, reasons = score + 8, reasons + ["description partly matches"]
    return min(score, 100), ", ".join(reasons)


def suggestions(conn: sqlite3.Connection) -> list[dict]:
    """The best one-to-one Links between unlinked Shared Expenses the user paid
    and unlinked Purchases, strongest first."""
    open_expenses = conn.execute(
        """SELECT id, date, description, total_cents FROM shared_expenses
           WHERE paid_by IS NULL AND transaction_id IS NULL AND standalone = 0"""
    ).fetchall()
    if not open_expenses:
        return []
    purchases = conn.execute(
        """SELECT t.id, t.date, t.description, t.amount_cents FROM transaction_view t
           WHERE t.effective_kind = 'purchase'
             AND NOT EXISTS (SELECT 1 FROM shared_expenses e WHERE e.transaction_id = t.id)"""
    ).fetchall()
    candidates = sorted(
        (
            (score, reason, tx, e)
            for e in open_expenses for tx in purchases
            for score, reason in [_score(tx, e)] if score >= _MIN_SCORE
        ),
        key=lambda c: (-c[0], c[3]["id"], c[2]["id"]),
    )
    used_tx, used_e, result = set(), set(), []
    for score, reason, tx, e in candidates:
        if tx["id"] in used_tx or e["id"] in used_e:
            continue
        used_tx.add(tx["id"])
        used_e.add(e["id"])
        result.append({"expense_id": e["id"], "transaction_id": tx["id"], "score": score, "reason": reason,
                       "expense": dict(e), "transaction": dict(tx)})
    return result
