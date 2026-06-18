import re

import pdfplumber

from backend.parsers.base import Transaction, clean_amount, normalize_date

DATE_RE = re.compile(r"\b(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})\b")
AMOUNT_RE = re.compile(r"[\-\+]?\$?[\d,]+\.\d{2}")


def parse(pdf_path: str) -> list[Transaction]:
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        row = [c or "" for c in row]
                        tx = _try_parse_row(row)
                        if tx:
                            transactions.append(tx)
            else:
                text = page.extract_text() or ""
                for line in text.split("\n"):
                    tx = _try_parse_line(line)
                    if tx:
                        transactions.append(tx)
    return transactions


def _try_parse_row(row: list[str]):
    date_col = amount_col = None
    for i, cell in enumerate(row):
        if DATE_RE.search(cell):
            date_col = i
        if AMOUNT_RE.search(cell):
            amount_col = i
    if date_col is None or amount_col is None:
        return None
    candidates = [
        (i, c)
        for i, c in enumerate(row)
        if i != date_col and i != amount_col and len(c) > 3
    ]
    if not candidates:
        return None
    desc_col = max(candidates, key=lambda x: len(x[1]))[0]
    try:
        amt = clean_amount(AMOUNT_RE.search(row[amount_col]).group())
        return Transaction(
            date=normalize_date(DATE_RE.search(row[date_col]).group()),
            description=row[desc_col].strip(),
            amount=abs(amt),
            tx_type="credit" if amt < 0 else "debit",
        )
    except Exception:
        return None


def _try_parse_line(line: str):
    date_m = DATE_RE.search(line)
    amount_m = AMOUNT_RE.search(line)
    if not date_m or not amount_m:
        return None
    description = line[date_m.end() : amount_m.start()].strip()
    if len(description) < 3:
        return None
    try:
        amt = clean_amount(amount_m.group())
        return Transaction(
            date=normalize_date(date_m.group()),
            description=description,
            amount=abs(amt),
            tx_type="credit" if amt < 0 else "debit",
        )
    except Exception:
        return None
