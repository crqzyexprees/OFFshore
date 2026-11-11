from datetime import date

import numpy as np
import pytest

from backend import ledger
from backend.config import MODEL_DIR
from backend.prediction import ExamplePredictor, clean, load
from backend.statement_import import Document, Page, import_statement

DAY = date(2026, 1, 15)


class WordsEmbedder:
    """Similar = shares words. Stands in for the sentence model."""

    def __init__(self):
        self.vocab: dict[str, int] = {}

    def embed(self, texts):
        vectors = np.zeros((len(texts), 256))
        for i, text in enumerate(texts):
            for word in text.split():
                vectors[i, self.vocab.setdefault(word, len(self.vocab))] = 1
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1, norms)


SEEDS = {"Groceries": ["whole foods market"], "Dining": ["blue bottle coffee"]}


def predictor(corrections=()):
    return ExamplePredictor(WordsEmbedder(), lambda: list(corrections), seeds=SEEDS)


@pytest.mark.parametrize("raw, merchant", [
    ("SQ *BLUE BOTTLE COFFEE 12345 OAKLAND CA", "blue bottle coffee oakland"),
    ("PURCHASE AUTHORIZED ON 12/10 TST* SHAKE SHACK NEW YORK NY", "shake shack new york"),
    ("NETFLIX.COM 866-579-7172", "netflix"),
    ("CHIPOTLE 1234", "chipotle"),
    ("12345", "12345"),
])
def test_clean_keeps_the_merchant(raw, merchant):
    assert clean(raw) == merchant


def test_nearest_example_wins():
    assert predictor().predict("WHOLE FOODS MKT #102", 4000, "purchase", DAY)[0] == "Groceries"
    assert predictor().predict("SQ *BLUE BOTTLE OAKLAND CA", 500, "purchase", DAY)[0] == "Dining"


def test_nothing_similar_is_other_with_no_confidence():
    assert predictor().predict("ZORBLAX 99", 500, "purchase", DAY) == ("Other", None)


def test_a_correction_beats_the_starter_examples():
    corrected = predictor([("WHOLE FOODS MKT #555 AUSTIN TX", "Dining")])
    # Same merchant, different store number: an exact match after cleaning.
    assert corrected.predict("WHOLE FOODS MKT #102 AUSTIN TX", 4000, "purchase", DAY) == ("Dining", 1.0)


def test_corrections_are_read_fresh_each_time():
    corrections = []
    p = ExamplePredictor(WordsEmbedder(), lambda: corrections, seeds=SEEDS)
    assert p.predict("ACME RENT", 100, "purchase", DAY)[0] == "Other"
    corrections.append(("ACME RENT", "Housing"))
    assert p.predict("ACME RENT", 100, "purchase", DAY) == ("Housing", 1.0)


def test_one_correction_carries_over_to_the_same_merchant(conn):
    ledger.add_account(conn, name="Card", kind="credit_card", bank="chase", last_four="1234")
    header = ["Chase Freedom", "Account ending in 1234", "Opening/Closing Date 12/05/25 - 01/04/26"]
    lines = ["12/10 ACME RENT CO 1,500.00", "12/20 ACME RENT CO 1,500.00", "12/21 SHOES 50.00"]
    p = ExamplePredictor(
        WordsEmbedder(), lambda: [(c["description"], c["category"]) for c in ledger.corrections(conn)], seeds=SEEDS
    )
    import_statement(conn, Document("s.pdf", [Page("\n".join(header + lines))]), predictor=p)
    first = ledger.transactions(conn)[-1]["id"]

    ledger.set_override(conn, first, kind=None, category="Housing", predictor=p)
    assert ledger.repredict(conn, p) == 1

    assert [(t["description"], t["category"], t["overridden"]) for t in ledger.transactions(conn)] == [
        ("SHOES", "Other", False),
        ("ACME RENT CO", "Housing", False),
        ("ACME RENT CO", "Housing", True),
    ]


@pytest.mark.skipif(not (MODEL_DIR / "embedder" / "model.onnx").exists(),
                    reason="embedding model not fetched (python -m backend.prediction.fetch)")
def test_the_real_embedding_model_reads_messy_descriptions():
    p = load(MODEL_DIR)
    assert isinstance(p, ExamplePredictor)
    got = [c for c, _ in p.predict_many([
        ("TRADER JOE S #552 QPS PORTLAND OR", 4000, "purchase", DAY),
        ("SQ *BLUE BOTTLE COFFEE OAKLAND CA", 500, "purchase", DAY),
        ("SHELL OIL 57444 HOUSTON TX", 4000, "purchase", DAY),
        ("CVS/PHARMACY #04512 DALLAS TX", 1200, "purchase", DAY),
    ])]
    assert got == ["Groceries", "Dining", "Transport", "Pharmacy"]
