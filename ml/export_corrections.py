import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path.home() / ".local" / "share" / "finance-app" / "finance.db"
OUT_PARQUET = "data/processed/combined.parquet"

conn = sqlite3.connect(DB_PATH)
corrections = pd.read_sql_query(
    """
    SELECT description, manual_category as category
    FROM transactions
    WHERE manually_overridden = 1
    """,
    conn,
)
conn.close()

if corrections.empty:
    print("No manual corrections found.")
    raise SystemExit(0)

new_data = corrections.rename(columns={"description": "merchant_text"})
new_data["amount"] = 0.0
new_data["hour"] = 12.0
new_data["day_of_week"] = 3.0
new_data["month"] = 6.0
new_data["use_chip"] = "unknown"
new_data["use_chip_enc"] = 3

existing = pd.read_parquet(OUT_PARQUET)
updated = pd.concat([existing, new_data], ignore_index=True)
updated.to_parquet(OUT_PARQUET, index=False)
print(f"Added {len(new_data)} corrections to training data")
