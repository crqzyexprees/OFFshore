"""The ledger: Accounts, Transactions, Spending and Overrides, read and written.

Every query over stored Transactions lives here, on top of `transaction_view`
(db.py), so the HTTP routes, the training export and the tests all use the same
definitions. Statement import writes Transactions itself (statement_import).
"""

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date

from backend.prediction import CategoryPredictor
from backend.vocabulary import ACCOUNT_KINDS, CATEGORIES, CATEGORIZED_KINDS, KINDS, has_category, sql_list


class LedgerError(Exception):
    """A request the ledger refuses; nothing was changed."""


class NotFound(LedgerError):
    pass


_open_units: set[int] = set()  # connections inside a unit of work


@contextmanager
def unit_of_work(conn: sqlite3.Connection):
    """One all-or-nothing write: committed when the block ends, rolled back
    if it raises. A unit opened inside another joins it, so only the
    outermost one commits; a refusal anywhere stores nothing."""
    if id(conn) in _open_units:
        yield conn
        return
    conn.commit()  # end any implicit transaction so BEGIN IMMEDIATE can start one
    conn.execute("BEGIN IMMEDIATE")
    _open_units.add(id(conn))
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        _open_units.discard(id(conn))


# ── Accounts ────────────────────────────────────────────────────────────────

def accounts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT id, name, kind, bank, last_four, color FROM accounts ORDER BY name")
    return [dict(r) for r in rows]


def add_account(
    conn: sqlite3.Connection, *, name: str, kind: str, bank: str,
    last_four: str | None = None, color: str = "#6366f1",
) -> int:
    if kind not in ACCOUNT_KINDS:
        raise LedgerError(f"Unknown account kind: {kind}")
    with unit_of_work(conn):
        return conn.execute(
            "INSERT INTO accounts (name, kind, bank, last_four, color) VALUES (?, ?, ?, ?, ?)",
            (name, kind, bank, last_four, color),
        ).lastrowid


def delete_account(conn: sqlite3.Connection, account_id: int) -> None:
    """Removes the Account with all its Statements and Transactions."""
    with unit_of_work(conn):
        conn.execute("DELETE FROM accounts WHERE id = ?", (account_id,))


# ── Statements ──────────────────────────────────────────────────────────────

def statements(conn: sqlite3.Connection) -> list[dict]:
    """Imported Statements, latest billing period first, with how many
    Transactions each holds and how many of those pay for a Shared Expense."""
    rows = conn.execute(
        """SELECT s.id, s.account_id, s.period_start, s.period_end, s.file_name, s.imported_at,
                  COUNT(t.id) AS transactions, COUNT(e.id) AS linked_shared
           FROM statements s LEFT JOIN transactions t ON t.statement_id = s.id
           LEFT JOIN shared_expenses e ON e.transaction_id = t.id
           GROUP BY s.id ORDER BY s.period_end DESC, s.id DESC"""
    )
    return [dict(r) for r in rows]


def delete_statement(conn: sqlite3.Connection, statement_id: int) -> list[dict]:
    """Removes the Statement and its Transactions, Overrides included.
    Returns the Shared Expenses its Purchases paid for: they're unlinked, so
    they wait on Reconcile again (docs/adr/0007)."""
    with unit_of_work(conn):
        unlinked = [dict(r) for r in conn.execute(
            """SELECT e.id, e.date, e.description FROM shared_expenses e
               JOIN transactions t ON t.id = e.transaction_id WHERE t.statement_id = ?""",
            (statement_id,),
        )]
        if conn.execute("DELETE FROM statements WHERE id = ?", (statement_id,)).rowcount == 0:
            raise NotFound("Statement not found")
    return unlinked


# ── Transactions ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TransactionFilter:
    account_id: int | None = None
    month: str | None = None  # "YYYY-MM"
    category: str | None = None
    kind: str | None = None


def transactions(conn: sqlite3.Connection, where: TransactionFilter = TransactionFilter()) -> list[dict]:
    """Transactions with their effective kind and Category, and the Shared
    Expense each one pays for, if any; newest first."""
    filters, params = [], []
    if where.account_id is not None:
        filters.append("account_id = ?")
        params.append(where.account_id)
    if where.month:
        filters.append("strftime('%Y-%m', date) = ?")
        params.append(where.month)
    if where.category:
        filters.append("effective_category = ?")
        params.append(where.category)
    if where.kind:
        filters.append("effective_kind = ?")
        params.append(where.kind)
    clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = conn.execute(
        f"""SELECT id, account_id, statement_id, date, description, amount_cents, direction,
                   effective_kind AS kind, effective_category AS category,
                   category_confidence, overridden, override_kind, override_category,
                   (SELECT e.id FROM shared_expenses e WHERE e.transaction_id = transaction_view.id)
                       AS shared_expense_id
            FROM transaction_view {clause} ORDER BY date DESC, id DESC""",
        params,
    )
    return [{**dict(r), "overridden": bool(r["overridden"])} for r in rows]


# ── Spending ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Spending:
    by_category: dict[str, int]  # cents; Purchases minus Refunds, largest first
    withdrawn_cents: int  # Withdrawals are not Spending but are shown beside it


def spending(conn: sqlite3.Connection, month: str) -> Spending:
    """Spending for one calendar month ("YYYY-MM"), from `spending_items` (db.py)."""
    rows = conn.execute(
        """SELECT category, SUM(cents) AS cents FROM spending_items
           WHERE strftime('%Y-%m', date) = ?
           GROUP BY category ORDER BY cents DESC, category""",
        (month,),
    ).fetchall()
    withdrawn = conn.execute(
        """SELECT COALESCE(SUM(amount_cents), 0) FROM transaction_view
           WHERE effective_kind = 'withdrawal' AND strftime('%Y-%m', date) = ?""",
        (month,),
    ).fetchone()[0]
    return Spending({r["category"]: r["cents"] for r in rows}, withdrawn)


# ── Budgets ─────────────────────────────────────────────────────────────────

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _check_month(month: str) -> None:
    if not _MONTH.match(month):
        raise LedgerError(f"Not a month (YYYY-MM): {month}")


def budgets(conn: sqlite3.Connection, month: str) -> dict[str, int]:
    """Each Category's Budget for a month: the latest one set in or before it."""
    _check_month(month)
    rows = conn.execute(
        """SELECT b.category, b.amount_cents FROM budgets b
           WHERE b.from_month = (SELECT MAX(from_month) FROM budgets
                                 WHERE category = b.category AND from_month <= ?)""",
        (month,),
    )
    return {r["category"]: r["amount_cents"] for r in rows if r["amount_cents"] is not None}


def set_budget(conn: sqlite3.Connection, category: str, month: str, amount_cents: int | None) -> None:
    """Sets a Category's Budget from `month` on; None ends it. Earlier months
    keep the Budget they had."""
    _check_month(month)
    if category not in CATEGORIES:
        raise LedgerError(f"Unknown Category: {category}")
    if amount_cents is not None and amount_cents <= 0:
        raise LedgerError("A Budget must be more than zero; clear it to remove it.")
    before = conn.execute(
        """SELECT amount_cents FROM budgets WHERE category = ? AND from_month < ?
           ORDER BY from_month DESC LIMIT 1""",
        (category, month),
    ).fetchone()
    with unit_of_work(conn):
        if (before["amount_cents"] if before else None) == amount_cents:
            # Same as the month before: this month just follows it.
            conn.execute("DELETE FROM budgets WHERE category = ? AND from_month = ?", (category, month))
        else:
            conn.execute(
                """INSERT INTO budgets (category, from_month, amount_cents) VALUES (?, ?, ?)
                   ON CONFLICT (category, from_month) DO UPDATE SET amount_cents = excluded.amount_cents""",
                (category, month, amount_cents),
            )


# ── Overrides ───────────────────────────────────────────────────────────────

def set_override(
    conn: sqlite3.Connection, tx_id: int, *, kind: str | None, category: str | None,
    predictor: CategoryPredictor | None = None,
) -> None:
    """Sets both parts of a Transaction's Override; None clears that part.

    When the Override makes a Transaction categorized for the first time (a
    Peer Transfer that was really rent, say), its Category is predicted then,
    since import only predicts for kinds that have one.
    """
    if kind is not None and kind not in KINDS:
        raise LedgerError(f"Unknown kind: {kind}")
    if category is not None and category not in CATEGORIES:
        raise LedgerError(f"Unknown Category: {category}")
    tx = conn.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)).fetchone()
    if tx is None:
        raise NotFound("Transaction not found")

    predicted, confidence = tx["category"], tx["category_confidence"]
    effective_kind = kind or tx["kind"]
    if effective_kind != "purchase":
        # A Link means "this Purchase paid for that Shared Expense"; another kind can't.
        shared = conn.execute("SELECT description FROM shared_expenses WHERE transaction_id = ?", (tx_id,)).fetchone()
        if shared:
            raise LedgerError(
                f"This Purchase pays for the shared expense \u201c{shared['description']}\u201d. "
                "Unlink it on Reconcile first."
            )
    if predicted is None and has_category(effective_kind) and predictor is not None:
        predicted, confidence = predictor.predict(
            tx["description"], tx["amount_cents"], effective_kind, date.fromisoformat(tx["date"])
        )
    with unit_of_work(conn):
        conn.execute(
            """UPDATE transactions SET override_kind = ?, override_category = ?,
                                       category = ?, category_confidence = ? WHERE id = ?""",
            (kind, category, predicted, confidence, tx_id),
        )


def repredict(conn: sqlite3.Connection, predictor: CategoryPredictor) -> int:
    """Predicts again the Category of every categorized Transaction the user
    hasn't set one for, so one correction carries over to the same merchant's
    other Transactions. Returns how many changed."""
    rows = conn.execute(
        f"""SELECT id, description, amount_cents, effective_kind AS kind, date, category, category_confidence
            FROM transaction_view
            WHERE override_category IS NULL AND effective_kind IN ({sql_list(CATEGORIZED_KINDS)})"""
    ).fetchall()
    predictions = predictor.predict_many(
        [(r["description"], r["amount_cents"], r["kind"], date.fromisoformat(r["date"])) for r in rows]
    )
    changed = [
        (category, confidence, r["id"])
        for r, (category, confidence) in zip(rows, predictions)
        if (category, confidence) != (r["category"], r["category_confidence"])
    ]
    with unit_of_work(conn):
        conn.executemany("UPDATE transactions SET category = ?, category_confidence = ? WHERE id = ?", changed)
    return len(changed)


# ── Training export ─────────────────────────────────────────────────────────

def corrections(conn: sqlite3.Connection) -> list[dict]:
    """Categorized Transactions whose Category the user set by hand: the
    labelled examples the classifier is retrained on."""
    rows = conn.execute(
        f"""SELECT description, amount_cents, effective_kind AS kind, date,
                   override_category AS category
            FROM transaction_view
            WHERE override_category IS NOT NULL
              AND effective_kind IN ({sql_list(CATEGORIZED_KINDS)})"""
    )
    return [dict(r) for r in rows]
