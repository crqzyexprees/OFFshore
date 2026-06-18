import hashlib
from dataclasses import asdict
from pathlib import Path

import pdfplumber

from backend.parsers.chase import parse as chase_parse
from backend.parsers.generic import parse as generic_parse

PARSERS = {
    "chase": chase_parse,
    "generic": generic_parse,
}


def detect_bank(pdf_path: str) -> str:
    with pdfplumber.open(pdf_path) as pdf:
        text = (pdf.pages[0].extract_text() or "").lower()
    if "chase" in text:
        return "chase"
    if "american express" in text:
        return "amex"
    if "citibank" in text:
        return "citi"
    if "bank of america" in text:
        return "bofa"
    if "wells fargo" in text:
        return "wellsfargo"
    if "capital one" in text:
        return "capitalone"
    return "generic"


def parse_statement(pdf_path: str) -> dict:
    path = Path(pdf_path)
    with open(path, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    bank = detect_bank(pdf_path)
    parse_fn = PARSERS.get(bank, generic_parse)

    try:
        transactions = parse_fn(pdf_path)
        return {
            "bank": bank,
            "file_hash": file_hash,
            "file_name": path.name,
            "transactions": [asdict(t) for t in transactions],
            "count": len(transactions),
            "error": None,
        }
    except Exception as e:
        return {
            "bank": bank,
            "file_hash": file_hash,
            "file_name": path.name,
            "transactions": [],
            "count": 0,
            "error": str(e),
        }
