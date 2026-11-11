"""Statement reading: the facts a Document states and the Transactions it lists.

Everything that depends on how banks print Statements lives here: which bank
it is, the Account's last four digits, the billing period, which lines are
Transaction rows, how their dates and amounts are written, and which way the
money moved. `read_rows` returns rows ready to store, or the reason each
rejected line couldn't be read.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from backend.statement_import.document import Document

BANKS = {
    "chase": "Chase",
    "amex": "American Express",
    "citi": "Citi",
    "bofa": "Bank of America",
    "wellsfargo": "Wells Fargo",
    "capitalone": "Capital One",
    "discover": "Discover",
    "other": "Other",
}

_BANK_MARKERS = (
    ("amex", "american express"),
    ("bofa", "bank of america"),
    ("wellsfargo", "wells fargo"),
    ("capitalone", "capital one"),
    ("citi", "citibank"),
    ("citi", "citi cards"),
    ("discover", "discover bank"),
    ("discover", "discover card"),
    ("chase", "chase"),
)

_DATE = r"(?:\d{1,2}/\d{1,2}/\d{2,4}|[A-Z][a-z]{2,8}\.? \d{1,2},? \d{4})"
_PERIOD_RANGE = re.compile(rf"({_DATE})\s*(?:-|–|—|to|through|thru)\s*({_DATE})", re.I)
_PERIOD_OPEN_CLOSE = re.compile(
    rf"opening\s+date:?\s*({_DATE}).*?closing\s+date:?\s*({_DATE})", re.I | re.S
)
_PERIOD_KEYWORD = re.compile(r"period|opening|closing|billing|statement|cycle", re.I)
_MAX_PERIOD_DAYS = 62

_LAST_FOUR = (
    re.compile(r"ending\s+in\s*:?\s*(\d{4})\b", re.I),
    re.compile(r"ending\s*:?\s*(\d{4})\b", re.I),
    re.compile(r"(?:[x*•]\s?){4,}[\s-]*(\d{4})\b", re.I),
)

_ROW_DATE = r"\d{1,2}/\d{1,2}(?:/\d{2,4})?"
_ROW_AMOUNT = r"\(?[-+]?\$?[-+]?[\d,]*\d\.\d{2}\)?(?:\s?CR\b|-)?"
# A Transaction line starts with its date (optionally a posting date too) and
# has an amount after the description; anything after that (a running
# balance) is ignored.
_LINE = re.compile(
    rf"^\s*({_ROW_DATE})(?:\s+{_ROW_DATE})?\s+(.+?)\s+({_ROW_AMOUNT})(?:\s|$)", re.I
)
_CELL_DATE = re.compile(rf"^\s*({_ROW_DATE})\s*$")
_CELL_AMOUNT = re.compile(rf"^\s*{_ROW_AMOUNT}\s*$", re.I)


@dataclass(frozen=True)
class RawRow:
    """A line that looks like a Transaction, as printed."""

    date: str
    description: str
    amount: str
    source: str


@dataclass(frozen=True)
class Row:
    """A Transaction row as read: when, what, how much and which way."""

    date: date
    description: str
    cents: int
    direction: str  # "in" | "out" of the Account


def detect_bank(document: Document) -> str | None:
    first_page = (document.pages[0].text if document.pages else "").lower()
    for bank, marker in _BANK_MARKERS:
        if marker in first_page:
            return bank
    return None


def find_last_four(document: Document) -> str | None:
    for pattern in _LAST_FOUR:
        if match := pattern.search(document.text):
            return match[1]
    return None


def find_period(document: Document) -> tuple[date, date] | None:
    text = document.text
    for line in text.splitlines():
        if _PERIOD_KEYWORD.search(line) and (match := _PERIOD_RANGE.search(line)):
            if period := _as_period(match[1], match[2]):
                return period
    if match := _PERIOD_OPEN_CLOSE.search(text):
        return _as_period(match[1], match[2])
    return None


def _as_period(start_text: str, end_text: str) -> tuple[date, date] | None:
    start, end = _parse_full_date(start_text), _parse_full_date(end_text)
    if start and end and start <= end and (end - start).days <= _MAX_PERIOD_DAYS:
        return start, end
    return None


def read_rows(
    document: Document, period: tuple[date, date], account_kind: str
) -> tuple[list[Row], list[dict]]:
    """The Transaction rows, and each line that looked like one but couldn't be
    read ({"line", "reason"}). Zero-amount rows are dropped."""
    start, end = period
    rows, rejected = [], []
    for raw in _find_rows(document):
        try:
            when = _resolve_date(raw.date, start, end)
            cents, negative = _parse_amount(raw.amount)
        except ValueError as e:
            rejected.append({"line": raw.source, "reason": str(e)})
            continue
        if cents:
            rows.append(Row(when, raw.description, cents, _direction(negative, account_kind)))
    return rows, rejected


def _direction(negative: bool, account_kind: str) -> str:
    # Credit card Statements print charges as positive and credits as negative;
    # bank Statements print money leaving the Account as negative.
    if account_kind == "credit_card":
        return "in" if negative else "out"
    return "out" if negative else "in"


def _find_rows(document: Document) -> list[RawRow]:
    rows: list[RawRow] = []
    for page in document.pages:
        from_tables = [row for table in page.tables for row in _rows_from_table(table)]
        rows.extend(from_tables or _rows_from_text(page.text))
    return rows


def _rows_from_text(text: str) -> list[RawRow]:
    rows = []
    for line in text.splitlines():
        if match := _LINE.match(line):
            rows.append(RawRow(match[1], match[2].strip(), match[3], line.strip()))
    return rows


def _rows_from_table(table: list[list[str]]) -> list[RawRow]:
    rows = []
    for cells in table:
        date_col = next((i for i, c in enumerate(cells) if _CELL_DATE.match(c)), None)
        if date_col is None:
            continue
        # The first amount after the date; a later one is the running balance.
        amount_col = next(
            (i for i in range(date_col + 1, len(cells)) if _CELL_AMOUNT.match(cells[i])), None
        )
        if amount_col is None:
            continue
        between = [c.strip() for c in cells[date_col + 1 : amount_col] if c.strip()]
        description = max(between, key=len, default="")
        if description:
            rows.append(
                RawRow(cells[date_col].strip(), description, cells[amount_col].strip(),
                       " | ".join(c.strip() for c in cells))
            )
    return rows


# ── Dates and amounts ──
# `_AMOUNT` must accept everything `_ROW_AMOUNT` finds (tests/test_statement_import.py checks it).

# A Transaction can happen a while before its billing period starts (it posts
# late), but never long after the period ends.
_EARLIEST_BEFORE_PERIOD = timedelta(days=45)
_LATEST_AFTER_PERIOD = timedelta(days=7)

_FULL_DATE_FORMATS = (
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y", "%Y-%m-%d",
    "%B %d %Y", "%b %d %Y", "%d %b %Y", "%d %B %Y",
)
_MONTH_DAY = re.compile(r"^(\d{1,2})[/-](\d{1,2})$")
_AMOUNT = re.compile(r"^(\()?\s*([-+])?\s*\$?\s*([-+])?\s*([\d,]*\d\.\d{2})\s*(\))?\s*(-|CR)?$", re.I)


def _parse_full_date(text: str) -> date | None:
    """A date that includes its year, or None."""
    cleaned = " ".join(text.replace(",", " ").replace(".", " ").split())
    for fmt in _FULL_DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _resolve_date(text: str, period_start: date, period_end: date) -> date:
    """The date a row happened. Dates printed without a year (Chase prints
    "10/14") take the year that puts them inside the billing period."""
    text = text.strip()
    window_start = period_start - _EARLIEST_BEFORE_PERIOD
    window_end = period_end + _LATEST_AFTER_PERIOD

    full = _parse_full_date(text)
    if full is not None:
        candidates = [full]
    elif match := _MONTH_DAY.match(text):
        month, day = int(match[1]), int(match[2])
        candidates = []
        for year in sorted({period_start.year, period_end.year}):
            try:
                candidates.append(date(year, month, day))
            except ValueError:
                pass
        if not candidates:
            raise ValueError(f"not a real date: {text!r}")
    else:
        raise ValueError(f"unrecognised date: {text!r}")

    for candidate in candidates:
        if window_start <= candidate <= window_end:
            return candidate
    raise ValueError(f"date {text!r} is outside the billing period")


def _parse_amount(text: str) -> tuple[int, bool]:
    """(cents, negative). Negative is written as -1.00, (1.00), 1.00- or 1.00 CR."""
    match = _AMOUNT.match(text.strip())
    if not match:
        raise ValueError(f"unrecognised amount: {text!r}")
    open_paren, sign1, sign2, digits, close_paren, suffix = match.groups()
    if bool(open_paren) != bool(close_paren):
        raise ValueError(f"unbalanced parentheses in amount: {text!r}")
    cents = int(round(float(digits.replace(",", "")) * 100))
    negative = bool(open_paren) or "-" in (sign1, sign2) or bool(suffix)
    return cents, negative
