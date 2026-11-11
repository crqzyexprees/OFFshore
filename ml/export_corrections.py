"""Writes the user's hand-set Categories to data/processed/corrections.parquet.

The file is rewritten each time (never appended to), and train.py reads it
alongside combined.parquet, so re-running either script never duplicates or
loses corrections.
"""

import pandas as pd

import _paths  # noqa: F401
from backend import ledger
from backend.config import DB_PATH
from backend.db import connect

OUT = "data/processed/corrections.parquet"

conn = connect(DB_PATH)
rows = ledger.corrections(conn)
conn.close()

df = pd.DataFrame(rows, columns=["description", "amount_cents", "kind", "date", "category"])
df["date"] = pd.to_datetime(df["date"]).dt.date
df.to_parquet(OUT, index=False)
print(f"Wrote {len(df)} corrections to {OUT}")
