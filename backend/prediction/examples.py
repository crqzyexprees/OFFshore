"""Predicting a Category from labelled examples: the user's own corrections,
plus a starter set (seeds.py) so it works before there are any.

A Transaction takes the Category of the most similar example, by meaning
(sentence embeddings), so "WHOLEFDS AUSTIN" finds "Whole Foods Market". The
user's corrections count for more than the starter set, and a description
the user has already categorised is matched exactly.
"""

import re
from collections import Counter
from collections.abc import Callable

from backend.prediction.base import Prediction, Query
from backend.prediction.seeds import SEEDS
from backend.vocabulary import CATEGORIES, FALLBACK_CATEGORY

# Below this similarity the nearest example is not a real match.
MIN_SIMILARITY = 0.35
# Starter examples are generic; the user's own corrections are about their merchants.
SEED_WEIGHT = 0.9

# Noise banks add around the merchant name.
_PREFIXES = re.compile(
    r"^(?:purchase authorized on|recurring payment authorized on|pos (?:debit|purchase)|"
    r"debit card purchase|checkcard|visa purchase|ach (?:debit|withdrawal))\b\s*", re.I
)
_PROCESSOR = re.compile(r"^(?:sq|tst|sp|pp|paypal|py|dd|bt|ic|sqsp)\s*\*\s*", re.I)
_HAS_DIGIT = re.compile(r"\S*\d\S*")
_US_STATE = re.compile(r"\s(?:a[klrz]|c[aot]|d[ce]|fl|ga|hi|i[adln]|k[sy]|la|m[adeinost]|n[cdehjmvy]|o[hkr]|pa|ri|s[cd]|t[nx]|ut|v[at]|w[aivy])$")


def clean(description: str) -> str:
    """The merchant part of a Statement description, lowercased.

    "SQ *BLUE BOTTLE COFFEE 12345 OAKLAND CA" → "blue bottle coffee oakland"
    """
    text = description.lower().strip()
    for _ in range(2):  # "PURCHASE AUTHORIZED ON 12/10 SQ *…" has both
        text = _PREFIXES.sub("", text)
        text = _HAS_DIGIT.sub(" ", text).strip()
        text = _PROCESSOR.sub("", text)
    text = re.sub(r"[*#]+|\.com\b|\s-\s", " ", text)
    text = " ".join(text.split())
    if len(text.split()) > 2:
        text = _US_STATE.sub("", text)
    return text or description.lower().strip()


Corrections = Callable[[], list[tuple[str, str]]]  # → [(description, Category)]


class ExamplePredictor:
    def __init__(self, embedder, corrections: Corrections, seeds: dict[str, list[str]] = SEEDS):
        self.embedder = embedder
        self.corrections = corrections
        self.seeds = [(clean(text), category) for category, texts in seeds.items() for text in texts]
        self._vectors: dict[str, object] = {}

    def _embed(self, texts: list[str]):
        import numpy as np

        missing = [t for t in dict.fromkeys(texts) if t not in self._vectors]
        if missing:
            for text, vector in zip(missing, self.embedder.embed(missing)):
                self._vectors[text] = vector
        return np.stack([self._vectors[t] for t in texts])

    def predict(self, description, amount_cents, kind, when):
        return self.predict_many([(description, amount_cents, kind, when)])[0]

    def predict_many(self, queries: list[Query]) -> list[Prediction]:
        """Only the description matters here: a Refund belongs to the same
        Category as the Purchase it reverses."""
        if not queries:
            return []
        descriptions = [q[0] for q in queries]
        mine = [(clean(d), c) for d, c in self.corrections() if c in CATEGORIES]
        exact: dict[str, Counter] = {}
        for text, category in mine:
            exact.setdefault(text, Counter())[category] += 1

        examples = mine + self.seeds
        weights = [1.0] * len(mine) + [SEED_WEIGHT] * len(self.seeds)
        queries = [clean(d) for d in descriptions]
        similarity = self._embed(queries) @ self._embed([t for t, _ in examples]).T

        results = []
        for i, query in enumerate(queries):
            if query in exact:
                results.append((exact[query].most_common(1)[0][0], 1.0))
                continue
            scored = similarity[i] * weights
            best = int(scored.argmax())
            if scored[best] < MIN_SIMILARITY:
                results.append((FALLBACK_CATEGORY, None))
            else:
                results.append((examples[best][1], round(float(scored[best]), 3)))
        return results
