"""Builds data/processed/combined.parquet from the raw Kaggle datasets.

Each row is one labelled Purchase or Refund, in the shape backend.prediction.encode
takes: description, amount_cents, kind, date, category (a curated Category).
"""

import os

import pandas as pd

from mcc_map import MCC_TO_CATEGORY, SPARKOV_TO_CATEGORY

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
os.makedirs(OUT_DIR, exist_ok=True)


def as_examples(description, signed_dollars, when, category) -> pd.DataFrame:
    df = pd.DataFrame({
        "description": description.fillna("").astype(str),
        "amount_cents": (signed_dollars.abs() * 100).round().astype("int64"),
        "kind": signed_dollars.lt(0).map({True: "refund", False: "purchase"}),
        "date": pd.to_datetime(when).dt.date,
        "category": category,
    })
    return df[df["category"].notna() & (df["amount_cents"] > 0)]


print("Loading Sparkov dataset...")
spark = pd.read_csv(f"{RAW_DIR}/credit_card_transactions.csv", low_memory=False)
spark = as_examples(
    spark["merchant"].str.replace(r"^fraud_", "", regex=True),
    spark["amt"],
    spark["trans_date_trans_time"],
    spark["category"].map(SPARKOV_TO_CATEGORY),
)

print("Loading IBM dataset (this is large, may take a few minutes)...")
ibm = pd.read_csv(
    f"{RAW_DIR}/credit_card_transactions-ibm_v2.csv",
    low_memory=False,
    usecols=["Year", "Month", "Day", "Amount", "MCC"],
)
ibm = as_examples(
    pd.Series("", index=ibm.index),  # this dataset has no merchant names
    ibm["Amount"].str.replace("$", "", regex=False).astype(float),
    pd.to_datetime(ibm[["Year", "Month", "Day"]]),
    ibm["MCC"].map(MCC_TO_CATEGORY),
)

combined = pd.concat([spark, ibm], ignore_index=True)
print(f"\nFinal dataset shape: {combined.shape}")
print(f"\nCategory distribution:\n{combined['category'].value_counts()}")
combined.to_parquet(f"{OUT_DIR}/combined.parquet", index=False)
print(f"\nSaved to {OUT_DIR}/combined.parquet")
