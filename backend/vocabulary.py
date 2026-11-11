"""The domain's fixed vocabularies (GLOSSARY.md), defined once.

The database schema, Statement import, the ledger and the UI (via
/api/reference) all take these from here.
"""

# Every Transaction is exactly one of these kinds, with its glossary name.
KINDS: dict[str, str] = {
    "purchase": "Purchase",
    "refund": "Refund",
    "internal_transfer": "Internal Transfer",
    "peer_transfer": "Peer Transfer",
    "income": "Income",
    "withdrawal": "Withdrawal",
    "reward": "Reward",
}

# Only these kinds have a Category, and only they count as Spending.
CATEGORIZED_KINDS: tuple[str, ...] = ("purchase", "refund")

ACCOUNT_KINDS: dict[str, str] = {
    "credit_card": "Credit card",
    "bank": "Bank account",
}

# The curated Category list.
CATEGORIES: tuple[str, ...] = (
    "Dining",
    "Education",
    "Entertainment",
    "Fees & Interest",
    "Groceries",
    "Health",
    "Home",
    "Housing",
    "Insurance",
    "Kids & Pets",
    "Other",
    "Personal Care",
    "Pharmacy",
    "Shopping",
    "Subscriptions",
    "Transport",
    "Travel",
    "Utilities",
)

FALLBACK_CATEGORY = "Other"


def has_category(kind: str) -> bool:
    return kind in CATEGORIZED_KINDS


def sql_list(values) -> str:
    """Values as a SQL literal list, for CHECK constraints and views."""
    return ", ".join(f"'{v}'" for v in values)
