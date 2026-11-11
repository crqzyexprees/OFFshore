"""Exports: the CSV and OFX/QFX files banks offer instead of a PDF Statement.

An Export already has its rows in columns, so unlike a Document there is
nothing to find in free text. What it may lack is what a Statement prints in
its header: an OFX file names its Account and period, a CSV file usually
names neither, and import then asks for them the same way it does for a PDF.

Which way money moved is the one thing Exports disagree on:
- OFX amounts are signed from the Account holder's side: negative is money out,
  for credit cards and bank accounts alike.
- CSV files with separate debit and credit columns say so by column.
- CSV files with one amount column don't say. Banks write money out as
  negative; card issuers differ (Chase writes Purchases as negative, Amex and
  Discover as positive), so for a credit card the more common sign is taken to
  be Purchases (`Export.directions`).
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from backend.statement_import.reading import _BANK_MARKERS

EXPORT_SUFFIXES = (".csv", ".ofx", ".qfx")

# Single amount column: negative means "out" (bank, OFX), or unknown until the
# Account's kind is known (a credit card CSV).
_OUT_IS_NEGATIVE = "out_is_negative"
_INFER = "infer"


@dataclass(frozen=True)
class ExportRow:
    date: date
    description: str
    cents: int
    negative: bool
    source: str


@dataclass(frozen=True)
class Export:
    file_name: str
    rows: list[ExportRow]
    rejected: list[dict] = field(default_factory=list)
    bank: str | None = None
    last_four: str | None = None
    period: tuple[date, date] | None = None
    signs: str = _OUT_IS_NEGATIVE

    def directions(self, account_kind: str) -> list[str]:
        """Which way each row's money moved, "in" or "out" of the Account."""
        out_is_negative = True
        if self.signs == _INFER and account_kind == "credit_card":
            negatives = sum(row.negative for row in self.rows)
            out_is_negative = negatives > len(self.rows) - negatives
        return ["out" if row.negative == out_is_negative else "in" for row in self.rows]


def is_export(file_name: str) -> bool:
    return file_name.lower().endswith(EXPORT_SUFFIXES)


def read_export(data: bytes, file_name: str) -> Export:
    """Raises ValueError when the file isn't a readable CSV or OFX file."""
    text = data.decode("utf-8-sig", errors="replace")
    if file_name.lower().endswith(".csv"):
        return _read_csv(text, file_name)
    return _read_ofx(text, file_name)


# ── CSV ──

_DATE_COLUMNS = ("transaction_date", "trans_date", "date", "posted_date", "post_date", "posting_date")
_DESCRIPTION_COLUMNS = ("description", "merchant", "name", "payee", "memo", "details")
_AMOUNT_COLUMNS = ("amount", "transaction_amount")
_DEBIT_COLUMNS = ("debit", "withdrawal", "withdrawals", "charge", "charges")
_CREDIT_COLUMNS = ("credit", "deposit", "deposits", "payment", "payments")

_CSV_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%Y/%m/%d")


def _read_csv(text: str, file_name: str) -> Export:
    try:
        lines = [row for row in csv.reader(io.StringIO(text), strict=True) if any(c.strip() for c in row)]
    except csv.Error as e:
        raise ValueError(f"The CSV file can't be read: {e}") from e
    if not lines:
        raise ValueError("The CSV file is empty.")

    header = [_column_name(c) for c in lines[0]]
    date_col = _first(header, _DATE_COLUMNS)
    description_col = _first(header, _DESCRIPTION_COLUMNS)
    amount_col = _first(header, _AMOUNT_COLUMNS)
    debit_col, credit_col = _first(header, _DEBIT_COLUMNS), _first(header, _CREDIT_COLUMNS)
    if date_col is None or description_col is None or (amount_col is None and debit_col is None):
        raise ValueError("The CSV file needs date, description and amount columns.")

    rows, rejected = [], []
    for cells in lines[1:]:
        source = ",".join(cells)
        cell = lambda i: cells[i].strip() if i is not None and i < len(cells) else ""  # noqa: E731
        try:
            when = _parse_csv_date(cell(date_col))
            description = cell(description_col)
            if not description:
                raise ValueError("no description")
            if amount_col is not None and cell(amount_col):
                cents, negative = _parse_money(cell(amount_col))
            elif cell(debit_col):
                cents, negative = _parse_money(cell(debit_col))
                negative = True  # a debit column is money out, however it's written
            elif cell(credit_col):
                cents, negative = _parse_money(cell(credit_col))
                negative = False
            else:
                raise ValueError("no amount")
        except ValueError as e:
            rejected.append({"line": source, "reason": str(e)})
            continue
        if cents:
            rows.append(ExportRow(when, description, cents, negative, source))

    signs = _OUT_IS_NEGATIVE if amount_col is None else _INFER
    return Export(file_name, rows, rejected, signs=signs)


def _column_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _first(header: list[str], candidates: tuple[str, ...]) -> int | None:
    return next((header.index(c) for c in candidates if c in header), None)


def _parse_csv_date(text: str) -> date:
    for fmt in _CSV_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unrecognised date: {text!r}")


_MONEY = re.compile(r"^(\()?\s*(-)?\s*\$?\s*(-)?\s*([\d,]*\d(?:\.\d{1,2})?)\s*(\))?$")


def _parse_money(text: str) -> tuple[int, bool]:
    """(cents, negative). Negative is written as -1.00 or (1.00)."""
    match = _MONEY.match(text.strip())
    if not match:
        raise ValueError(f"unrecognised amount: {text!r}")
    open_paren, sign1, sign2, digits, close_paren = match.groups()
    if bool(open_paren) != bool(close_paren):
        raise ValueError(f"unbalanced parentheses in amount: {text!r}")
    cents = int(round(float(digits.replace(",", "")) * 100))
    return cents, bool(open_paren) or bool(sign1 or sign2)


# ── OFX / QFX ──
# OFX 1.x is SGML whose leaf tags are often left unclosed (<TRNAMT>-4.50), and
# 2.x is XML; reading a tag's value up to the next "<" or line end covers both.

_TRANSACTION = re.compile(r"<STMTTRN>(.*?)(?=<STMTTRN>|</STMTTRN>|</BANKTRANLIST>|$)", re.I | re.S)


def _tag(block: str, tag: str) -> str:
    match = re.search(rf"<{tag}>([^<\r\n]*)", block, re.I)
    return match[1].strip() if match else ""


def _parse_ofx_date(text: str) -> date:
    if not re.match(r"^\d{8}", text):
        raise ValueError(f"unrecognised date: {text!r}")
    return datetime.strptime(text[:8], "%Y%m%d").date()


def _read_ofx(text: str, file_name: str) -> Export:
    if not re.search(r"<OFX>", text, re.I):
        raise ValueError("The file isn't an OFX/QFX file.")

    rows, rejected = [], []
    for block in _TRANSACTION.findall(text):
        source = " ".join(block.split())[:200]
        try:
            when = _parse_ofx_date(_tag(block, "DTUSER") or _tag(block, "DTPOSTED"))
            cents, negative = _parse_money(_tag(block, "TRNAMT"))
            description = _tag(block, "NAME") or _tag(block, "MEMO")
            if not description:
                raise ValueError("no description")
        except ValueError as e:
            rejected.append({"line": source, "reason": str(e)})
            continue
        if cents:
            rows.append(ExportRow(when, description, cents, negative, source))

    period = None
    try:
        start, end = _parse_ofx_date(_tag(text, "DTSTART")), _parse_ofx_date(_tag(text, "DTEND"))
        if start <= end:
            period = (start, end)
    except ValueError:
        pass

    account_number = re.sub(r"\D", "", _tag(text, "ACCTID"))
    organisation = (_tag(text, "ORG") + " " + _tag(text, "BANKID")).lower()
    bank = next((b for b, marker in _BANK_MARKERS if marker in organisation), None)
    return Export(
        file_name, rows, rejected,
        bank=bank,
        last_four=account_number[-4:] if len(account_number) >= 4 else None,
        period=period,
    )
