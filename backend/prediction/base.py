"""What every Category predictor offers, and the predictor used when there's none."""

from datetime import date
from typing import Protocol

from backend.vocabulary import CATEGORIES, FALLBACK_CATEGORY


Prediction = tuple[str, float | None]  # (Category, confidence); None: not a real guess
Query = tuple[str, int, str, date]  # description, amount_cents, kind, date


class CategoryPredictor(Protocol):
    def predict(self, description: str, amount_cents: int, kind: str, when: date) -> Prediction: ...

    def predict_many(self, queries: list[Query]) -> list[Prediction]:
        """`predict` for many Transactions; adapters may batch it."""
        ...


class OneAtATime:
    """`predict_many` for adapters with nothing to gain from batching."""

    def predict_many(self, queries: list[Query]) -> list[Prediction]:
        return [self.predict(*q) for q in queries]


class NoModel(OneAtATime):
    """Used when no model is installed."""

    def predict(self, description, amount_cents, kind, when):
        return FALLBACK_CATEGORY, None


def to_category(label: str, confidence: float) -> tuple[str, float | None]:
    """A model label as a curated Category. A label outside the list is not a
    real prediction, so it carries no confidence."""
    if label in CATEGORIES:
        return label, confidence
    return FALLBACK_CATEGORY, None
