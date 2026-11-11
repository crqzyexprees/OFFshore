"""Splitwise import: a group or friend export (CSV) becomes Shared Expenses and
Settlements between the user and the People in it.

A Splitwise export has Date, Description, Category, Cost and Currency columns,
then one column per member holding that member's *net* for the row: what they
paid minus their Share. Nets sum to zero. With a single payer that is enough
to recover every Share (docs/adr/0007):

    someone who didn't pay:  Share = -net
    the payer:               Share = Cost - net

"Payment" rows are Settlements. Every row is keyed by its contents, so
importing a file again only adds the rows that are new.
"""

import csv
import hashlib
import io
import re
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from backend import sharing
from backend.ledger import LedgerError
from backend.prediction import CategoryPredictor, NoModel
from backend.vocabulary import CATEGORIES, FALLBACK_CATEGORY

_STANDARD = {"date", "description", "category", "cost", "currency", "notes", "note", "details"}

# Splitwise's categories, by the name it exports, mapped to SplitLens's.
# "General" and the "- Other" catch-alls aren't mapped: the description decides.
CATEGORY_MAP = {
    "dining out": "Dining", "food and drink - other": "Dining", "liquor": "Dining",
    "groceries": "Groceries",
    "rent": "Housing", "mortgage": "Housing",
    "household supplies": "Home", "furniture": "Home", "maintenance": "Home", "cleaning": "Home",
    "home - other": "Home",
    "pets": "Kids & Pets", "childcare": "Kids & Pets",
    "electronics": "Shopping", "clothing": "Shopping", "gifts": "Shopping",
    "electricity": "Utilities", "heat/gas": "Utilities", "water": "Utilities", "trash": "Utilities",
    "tv/phone/internet": "Utilities", "utilities - other": "Utilities",
    "parking": "Transport", "car": "Transport", "gas/fuel": "Transport", "bus/train": "Transport",
    "taxi": "Transport", "bicycle": "Transport", "transportation - other": "Transport",
    "plane": "Travel", "hotel": "Travel",
    "games": "Entertainment", "movies": "Entertainment", "music": "Entertainment",
    "sports": "Entertainment", "entertainment - other": "Entertainment",
    "education": "Education", "insurance": "Insurance", "medical expenses": "Health",
    "taxes": "Fees & Interest",
}


class SplitwiseError(LedgerError):
    """The file can't be imported as asked. Nothing was stored."""


@dataclass(frozen=True)
class Row:
    line: str
    date: date
    description: str
    category: str  # as Splitwise wrote it
    cost_cents: int
    currency: str
    nets: dict[str, int]  # member name -> net cents

    @property
    def is_payment(self) -> bool:
        return self.category.strip().lower() == "payment"


@dataclass(frozen=True)
class SplitwiseFile:
    members: list[str]
    rows: list[Row]
    rejected: list[dict] = field(default_factory=list)


def read_splitwise(data: bytes) -> SplitwiseFile:
    text = data.decode("utf-8-sig", errors="replace")
    try:
        lines = [r for r in csv.reader(io.StringIO(text), strict=True) if any(c.strip() for c in r)]
    except csv.Error as e:
        raise SplitwiseError(f"The file can't be read as CSV: {e}") from e
    if not lines:
        raise SplitwiseError("The file is empty.")
    header = [h.strip() for h in lines[0]]
    lower = [h.lower() for h in header]
    if not {"date", "description", "cost"} <= set(lower):
        raise SplitwiseError("This doesn't look like a Splitwise export: it needs Date, Description and Cost columns.")
    members = [h for h in header if h and h.lower() not in _STANDARD]
    if not members:
        raise SplitwiseError("This Splitwise export has no member columns. Export it from a group or a friend's page.")

    col = {h: i for i, h in enumerate(lower)}
    member_col = {m: header.index(m) for m in members}
    rows, rejected = [], []
    for cells in lines[1:]:
        source = ",".join(cells)
        get = lambda i: cells[i].strip() if i is not None and i < len(cells) else ""  # noqa: E731
        description = get(col.get("description"))
        if not description or description.lower().startswith("total balance"):
            continue
        try:
            when = _parse_date(get(col["date"]))
            cost = abs(_cents(get(col["cost"])))
            nets = {m: _cents(get(i) or "0") for m, i in member_col.items()}
        except ValueError as e:
            rejected.append({"line": source, "reason": str(e)})
            continue
        if cost:
            rows.append(Row(source, when, description, get(col.get("category")), cost,
                            get(col.get("currency")) or "USD", nets))
    return SplitwiseFile(members, rows, rejected)


def _parse_date(text: str) -> date:
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"unrecognised date: {text!r}")


def _cents(text: str) -> int:
    cleaned = re.sub(r"[$,\s]", "", text)
    negative = cleaned.startswith("-") or (cleaned.startswith("(") and cleaned.endswith(")"))
    cleaned = cleaned.strip("()-+")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", cleaned):
        raise ValueError(f"unrecognised amount: {text!r}")
    cents = round(float(cleaned) * 100)
    return -cents if negative else cents


@dataclass
class ImportResult:
    imported: int = 0
    settlements: int = 0
    already_imported: int = 0
    not_involving_you: int = 0
    skipped: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {**self.__dict__}


def import_splitwise(
    conn: sqlite3.Connection,
    file: SplitwiseFile,
    *,
    your_name: str,
    group_name: str | None = None,
    predictor: CategoryPredictor = NoModel(),
) -> ImportResult:
    """Imports every row that involves the user. All or nothing: a failure
    stores none of it."""
    if your_name not in file.members:
        raise SplitwiseError(f"Choose which member is you: {', '.join(file.members)}.")
    result = ImportResult(skipped=list(file.rejected))
    others = [m for m in file.members if m != your_name]

    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        person = {m: _person(conn, m) for m in others}
        group_id = None
        if group_name and group_name.strip():
            group_id = _group(conn, group_name, person.values())
        seen: Counter = Counter()
        for row in file.rows:
            identity = _identity(row)
            seen[identity] += 1
            key = f"splitwise:{identity}#{seen[identity]}"
            if _already(conn, key):
                result.already_imported += 1
            elif row.currency.upper() != "USD":
                result.skipped.append({"line": row.line, "reason": f"in {row.currency}; only US dollars are tracked"})
            elif row.is_payment:
                if _import_payment(conn, row, your_name, person, key):
                    result.settlements += 1
                else:
                    result.not_involving_you += 1
            else:
                outcome = _import_expense(conn, row, your_name, person, group_id, key, predictor)
                if outcome is None:
                    result.not_involving_you += 1
                elif isinstance(outcome, str):
                    result.skipped.append({"line": row.line, "reason": outcome})
                else:
                    result.imported += 1
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    return result


def _identity(row: Row) -> str:
    nets = ",".join(f"{m}={c}" for m, c in sorted(row.nets.items()))
    raw = f"{row.date.isoformat()}|{row.description}|{row.cost_cents}|{row.currency}|{nets}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def _already(conn, key: str) -> bool:
    return bool(
        conn.execute("SELECT 1 FROM shared_expenses WHERE source_key = ?", (key,)).fetchone()
        or conn.execute("SELECT 1 FROM settlements WHERE source_key = ?", (key,)).fetchone()
    )


def _person(conn, name: str) -> int:
    row = conn.execute("SELECT id FROM people WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
    if row:
        return row["id"]
    return conn.execute("INSERT INTO people (name, note) VALUES (?, 'From Splitwise')", (name,)).lastrowid


def _group(conn, name: str, member_ids) -> int:
    row = conn.execute("SELECT id FROM groups WHERE name = ? COLLATE NOCASE", (name.strip(),)).fetchone()
    group_id = row["id"] if row else conn.execute("INSERT INTO groups (name) VALUES (?)", (name.strip(),)).lastrowid
    conn.executemany("INSERT OR IGNORE INTO group_members (group_id, person_id) VALUES (?, ?)",
                     [(group_id, p) for p in member_ids])
    return group_id


def _import_payment(conn, row: Row, you: str, person: dict[str, int], key: str) -> bool:
    """A Settlement between the user and one member, or False if it's between others."""
    mine = row.nets.get(you, 0)
    if mine == 0:
        return False
    # The other side is whoever moved the opposite way.
    other = max((m for m in person if row.nets.get(m, 0) * mine < 0),
                key=lambda m: abs(row.nets[m]), default=None)
    if other is None:
        return False
    sharing.add_settlement(conn, date=row.date.isoformat(), person_id=person[other], cents=abs(mine),
                           direction="to_them" if mine > 0 else "from_them",
                           note=row.description, source_key=key, commit=False)
    return True


def _import_expense(conn, row, you, person, group_id, key, predictor):
    """The new expense's id; None when the user isn't part of it; a reason
    (str) when the user's Share can't be worked out."""
    mine = row.nets.get(you, 0)
    payers = [m for m, net in row.nets.items() if net > 0]
    category = _category(row, predictor)
    common = dict(date=row.date.isoformat(), description=row.description, category=category,
                  total_cents=row.cost_cents, group_id=group_id, source_key=key)

    if payers == [you]:
        shares = {person[m]: -net for m, net in row.nets.items() if m != you and net < 0}
        your_share = row.cost_cents - mine
        if your_share < 0 or your_share + sum(shares.values()) != row.cost_cents:
            return "the member amounts don't add up to the cost"
        return sharing.add_expense(conn, sharing.NewExpense(your_share_cents=your_share, shares=shares, **common),
                                   commit=False)
    if mine < 0 and payers:
        # Someone else paid (with several payers, the one who paid most).
        payer = max(payers, key=lambda m: row.nets[m])
        return sharing.add_expense(conn, sharing.NewExpense(your_share_cents=-mine, paid_by=person[payer], **common),
                                   commit=False)
    if mine > 0:
        return "several people paid, so your share can't be worked out; add it by hand"
    return None


def _category(row: Row, predictor: CategoryPredictor) -> str:
    mapped = CATEGORY_MAP.get(row.category.strip().lower())
    if mapped:
        return mapped
    predicted, _ = predictor.predict(row.description, row.cost_cents, "purchase", row.date)
    return predicted if predicted in CATEGORIES else FALLBACK_CATEGORY
