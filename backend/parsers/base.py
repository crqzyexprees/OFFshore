from dataclasses import dataclass
from typing import Optional


@dataclass
class Transaction:
    date: str
    description: str
    amount: float
    tx_type: str
    use_chip: Optional[str] = None


def clean_amount(s: str) -> float:
    s = s.strip().replace(",", "").replace("$", "")
    if s.startswith("(") and s.endswith(")"):
        return -float(s[1:-1])
    return float(s)


def normalize_date(date_str: str) -> str:
    from datetime import datetime

    formats = [
        "%m/%d/%Y",
        "%m/%d/%y",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
        "%d %b %Y",
        "%m-%d-%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str
