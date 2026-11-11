"""Measures how well the app predicts Categories on your own Transactions.

1. Export what's in the app, with its current Category filled in:
       python evaluate.py export labelled.csv
2. Open labelled.csv and fix the `category` column wherever it's wrong
   (leave rows you're unsure about blank; they're skipped).
3. Score the predictor against your labels:
       python evaluate.py score labelled.csv

Scoring reports two numbers:
- starter only: no corrections at all, i.e. a brand-new install;
- with your other labels: each row predicted from every *other* labelled row
  (leave-one-out), i.e. how it does once you've been correcting for a while.
Only the backend's dependencies are needed, not torch.
"""

import csv
import sys
from collections import Counter
from datetime import date

import _paths  # noqa: F401
from backend import ledger
from backend.config import DB_PATH, MODEL_DIR
from backend.db import connect
from backend.prediction import ExamplePredictor, load
from backend.vocabulary import CATEGORIES

FIELDS = ["date", "description", "amount_cents", "kind", "category"]


def export(path: str) -> None:
    conn = connect(DB_PATH)
    rows = [t for t in ledger.transactions(conn) if t["category"] is not None]
    conn.close()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} Purchases and Refunds to {path}. Fix the category column, then run: score {path}")


def score(path: str) -> None:
    with open(path, newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["category"].strip()]
    unknown = {r["category"] for r in rows} - set(CATEGORIES)
    if unknown:
        sys.exit(f"Not curated Categories: {sorted(unknown)}")
    queries = [(r["description"], int(r["amount_cents"]), r["kind"], date.fromisoformat(r["date"])) for r in rows]
    truth = [r["category"] for r in rows]

    starter = load(MODEL_DIR)
    if not isinstance(starter, ExamplePredictor):
        sys.exit("The embedding model isn't installed: python -m backend.prediction.fetch")
    report("starter only", truth, [c for c, _ in starter.predict_many(queries)], rows)

    predicted = []
    for i, query in enumerate(queries):
        others = [(r["description"], r["category"]) for j, r in enumerate(rows) if j != i]
        p = ExamplePredictor(starter.embedder, lambda o=others: o)
        p._vectors = starter._vectors  # share the embedding cache
        predicted.append(p.predict(*query)[0])
    report("with your other labels", truth, predicted, rows)


def report(title, truth, predicted, rows) -> None:
    right = sum(t == p for t, p in zip(truth, predicted))
    print(f"\n── {title}: {right}/{len(truth)} = {right / len(truth):.0%} ──")
    misses = Counter((t, p) for t, p in zip(truth, predicted) if t != p)
    for (t, p), n in misses.most_common(8):
        example = next(r["description"] for r, tt, pp in zip(rows, truth, predicted) if (tt, pp) == (t, p))
        print(f"  {n:3}× {t} predicted as {p}   e.g. {example}")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("export", "score"):
        sys.exit(__doc__)
    {"export": export, "score": score}[sys.argv[1]](sys.argv[2])
