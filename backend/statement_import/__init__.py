"""Statement import: turns a Document into a stored Statement and its Transactions.

One call does everything a Statement needs before it can be trusted: match its
Account, find its billing period, validate each row, decide each Transaction's
kind and Category, and store it, replacing an earlier import of the same
period while carrying its Overrides over (docs/adr/0005).
"""

import sqlite3
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date

from backend.prediction import CategoryPredictor, NoModel
from backend.statement_import.document import Document, Page, read_pdf
from backend.statement_import.exports import Export, ExportRow, is_export, read_export
from backend.statement_import.kinds import OtherAccounts, decide_kind
from backend.statement_import.reading import (
    _EARLIEST_BEFORE_PERIOD, _LATEST_AFTER_PERIOD, BANKS, Row, detect_bank, find_last_four, find_period, read_rows,
)
from backend.vocabulary import has_category

__all__ = [
    "BANKS", "Document", "Page", "read_pdf", "Export", "ExportRow", "is_export", "read_export",
    "import_statement",
    "ImportResult", "ImportProblem", "NeedsAccount", "NeedsPeriod",
    "AccountMismatch", "NoTransactions", "PROBLEMS",
]


class ImportProblem(Exception):
    """The Statement can't be imported as asked. Nothing was stored.

    Each kind of problem declares the fields it carries in FIELDS; the UI's
    `ImportProblem` union (src/lib/db.ts) mirrors them, and a test keeps the
    two in step.
    """

    code = "import_failed"
    FIELDS: tuple[str, ...] = ()

    def __init__(self, message: str, **fields):
        if set(fields) != set(self.FIELDS):
            raise TypeError(f"{type(self).__name__} takes {self.FIELDS}, got {tuple(fields)}")
        super().__init__(message)
        self.fields = fields

    def to_json(self) -> dict:
        return {"problem": self.code, "message": str(self), **self.fields}


class NeedsAccount(ImportProblem):
    code = "needs_account"
    FIELDS = ("bank", "last_four")


class NeedsPeriod(ImportProblem):
    code = "needs_period"
    FIELDS = ("account_id",)


class AccountMismatch(ImportProblem):
    code = "account_mismatch"
    FIELDS = ("bank", "last_four")


class NoTransactions(ImportProblem):
    code = "no_transactions"
    FIELDS = ("rejected",)


PROBLEMS = (ImportProblem, NeedsAccount, NeedsPeriod, AccountMismatch, NoTransactions)


@dataclass
class UnmatchedOverride:
    """An Override from the replaced Statement with no matching Transaction."""

    date: str
    description: str
    amount_cents: int
    direction: str
    override_kind: str | None
    override_category: str | None


@dataclass
class ImportResult:
    statement_id: int
    account_id: int
    bank: str | None
    period_start: date
    period_end: date
    imported: int
    replaced: bool
    rejected: list[dict] = field(default_factory=list)
    unmatched_overrides: list[UnmatchedOverride] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            **asdict(self),
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


def import_statement(
    conn: sqlite3.Connection,
    document: Document | Export,
    *,
    account_id: int | None = None,
    period: tuple[date, date] | None = None,
    predictor: CategoryPredictor = NoModel(),
) -> ImportResult:
    exported = isinstance(document, Export)
    bank = document.bank if exported else detect_bank(document)
    last_four = document.last_four if exported else find_last_four(document)
    account = _resolve_account(conn, account_id, bank, last_four)

    period = period or (document.period if exported else find_period(document))
    if period is None:
        raise NeedsPeriod(
            "The billing period isn't printed in a form we recognise. Enter it to continue.",
            account_id=account["id"],
        )
    start, end = period
    if start > end:
        raise ImportProblem("The billing period ends before it starts.")

    others = _other_accounts(conn, account["id"])
    if exported:
        rows, rejected = _export_rows(document, period, account["kind"])
    else:
        rows, rejected = read_rows(document, period, account["kind"])
    kinds = [decide_kind(row.description, row.direction, account["kind"], others) for row in rows]
    categorized = [(row.description, row.cents, kind, row.date) for row, kind in zip(rows, kinds) if has_category(kind)]
    predictions = iter(predictor.predict_many(categorized))
    transactions = [
        (row.date.isoformat(), row.description, row.cents, row.direction, kind,
         *(next(predictions) if has_category(kind) else (None, None)))
        for row, kind in zip(rows, kinds)
    ]

    if not transactions:
        raise NoTransactions(
            "No Transactions were found in this Statement. Nothing was imported.",
            rejected=rejected,
        )

    statement_id, replaced, unmatched = _store(conn, account["id"], start, end, document.file_name, transactions)
    return ImportResult(
        statement_id=statement_id,
        account_id=account["id"],
        bank=bank,
        period_start=start,
        period_end=end,
        imported=len(transactions),
        replaced=replaced,
        rejected=rejected,
        unmatched_overrides=unmatched,
    )


def _export_rows(export: Export, period, account_kind) -> tuple[list[Row], list[dict]]:
    """An Export's rows inside the billing period, with the same allowance for
    late-posting Transactions as a PDF; rows outside it belong to another
    Statement and are rejected so two Exports can't store them twice."""
    start, end = period
    earliest, latest = start - _EARLIEST_BEFORE_PERIOD, end + _LATEST_AFTER_PERIOD
    rows, rejected = [], list(export.rejected)
    for row, direction in zip(export.rows, export.directions(account_kind)):
        if earliest <= row.date <= latest:
            rows.append(Row(row.date, row.description, row.cents, direction))
        else:
            rejected.append({"line": row.source, "reason": f"date {row.date.isoformat()} is outside the billing period"})
    return rows, rejected


def _resolve_account(conn, account_id, bank, last_four) -> sqlite3.Row:
    detected = {"bank": bank, "last_four": last_four}
    if account_id is None:
        if last_four is None:
            raise NeedsAccount("Choose which Account this Statement belongs to.", **detected)
        matches = conn.execute(
            "SELECT * FROM accounts WHERE last_four = ? AND (? IS NULL OR bank IN (?, 'other'))",
            (last_four, bank, bank),
        ).fetchall()
        if len(matches) != 1:
            raise NeedsAccount("Choose which Account this Statement belongs to.", **detected)
        return matches[0]

    account = conn.execute("SELECT * FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if account is None:
        raise ImportProblem("That Account doesn't exist.")
    if last_four and account["last_four"] and last_four != account["last_four"]:
        raise AccountMismatch(
            f"This Statement is for an account ending in {last_four}, "
            f"but {account['name']} ends in {account['last_four']}.",
            **detected,
        )
    if bank and account["bank"] not in (bank, "other"):
        raise AccountMismatch(
            f"This looks like a {BANKS[bank]} Statement, "
            f"but {account['name']} is a {BANKS.get(account['bank'], account['bank'])} Account.",
            **detected,
        )
    return account


def _other_accounts(conn, account_id: int) -> OtherAccounts:
    kinds = {r[0] for r in conn.execute("SELECT kind FROM accounts WHERE id != ?", (account_id,))}
    return OtherAccounts(bank="bank" in kinds, credit_card="credit_card" in kinds)


def _store(conn, account_id, start, end, file_name, transactions):
    """Store atomically, replacing an earlier import of the same period."""
    conn.commit()  # end any implicit transaction so BEGIN IMMEDIATE can start one
    conn.execute("BEGIN IMMEDIATE")
    try:
        old = conn.execute(
            "SELECT id FROM statements WHERE account_id = ? AND period_start = ? AND period_end = ?",
            (account_id, start.isoformat(), end.isoformat()),
        ).fetchone()
        overrides = defaultdict(list)
        if old:
            for r in conn.execute(
                """SELECT date, description, amount_cents, direction, override_kind, override_category
                   FROM transactions WHERE statement_id = ?
                     AND (override_kind IS NOT NULL OR override_category IS NOT NULL)""",
                (old["id"],),
            ):
                key = (r["date"], r["description"], r["amount_cents"], r["direction"])
                overrides[key].append((r["override_kind"], r["override_category"]))
            conn.execute("DELETE FROM statements WHERE id = ?", (old["id"],))

        statement_id = conn.execute(
            "INSERT INTO statements (account_id, period_start, period_end, file_name) VALUES (?, ?, ?, ?)",
            (account_id, start.isoformat(), end.isoformat(), file_name),
        ).lastrowid

        for when, description, cents, direction, kind, category, confidence in transactions:
            # Identical Transactions (two $4.50 coffees) each take one Override.
            pending = overrides.get((when, description, cents, direction))
            override_kind, override_category = pending.pop(0) if pending else (None, None)
            conn.execute(
                """INSERT INTO transactions
                   (statement_id, account_id, date, description, amount_cents, direction,
                    kind, category, category_confidence, override_kind, override_category)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (statement_id, account_id, when, description, cents, direction,
                 kind, category, confidence, override_kind, override_category),
            )

        unmatched = [
            UnmatchedOverride(*key, o_kind, o_category)
            for key, remaining in overrides.items()
            for o_kind, o_category in remaining
        ]
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return statement_id, old is not None, unmatched
