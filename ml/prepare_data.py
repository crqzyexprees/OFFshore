import os

import numpy as np
import pandas as pd

from mcc_map import MCC_TO_CATEGORY, SPARKOV_TO_CATEGORY

RAW_DIR = "data/raw"
OUT_DIR = "data/processed"
os.makedirs(OUT_DIR, exist_ok=True)

print("Loading Sparkov dataset...")
spark = pd.read_csv(f"{RAW_DIR}/credit_card_transactions.csv", low_memory=False)

spark = spark[["trans_date_trans_time", "merchant", "category", "amt"]].copy()
spark.columns = ["datetime", "merchant_text", "raw_category", "amount"]

spark["category"] = spark["raw_category"].map(SPARKOV_TO_CATEGORY).fillna("Other")
spark["datetime"] = pd.to_datetime(spark["datetime"])
spark["hour"] = spark["datetime"].dt.hour
spark["day_of_week"] = spark["datetime"].dt.dayofweek
spark["month"] = spark["datetime"].dt.month
spark["use_chip"] = "unknown"

spark["merchant_text"] = (
    spark["merchant_text"]
    .str.replace(r"^fraud_", "", regex=True)
    .str.lower()
    .str.strip()
)

print("Loading IBM dataset (this is large, may take a few minutes)...")
ibm = pd.read_csv(
    f"{RAW_DIR}/credit_card_transactions-ibm_v2.csv",
    low_memory=False,
    usecols=["Year", "Month", "Day", "Time", "Amount", "Use Chip", "MCC"],
)

ibm["amount"] = ibm["Amount"].str.replace("$", "", regex=False).astype(float)
ibm["hour"] = ibm["Time"].str.split(":").str[0].astype(int)
ibm["day_of_week"] = pd.to_datetime(ibm[["Year", "Month", "Day"]]).dt.dayofweek
ibm["month"] = ibm["Month"]
ibm["use_chip"] = ibm["Use Chip"].str.lower().str.strip()
ibm["category"] = ibm["MCC"].map(MCC_TO_CATEGORY).fillna("Other")
ibm["merchant_text"] = ""

COLS = ["merchant_text", "amount", "hour", "day_of_week", "month", "use_chip", "category"]

combined = pd.concat([spark[COLS], ibm[COLS]], ignore_index=True)

combined = combined.dropna(subset=["category"])
combined = combined[combined["amount"] != 0]

chip_map = {
    "swipe transaction": 0,
    "chip transaction": 1,
    "online transaction": 2,
    "unknown": 3,
}
combined["use_chip_enc"] = combined["use_chip"].map(chip_map).fillna(3).astype(int)

print(f"\nFinal dataset shape: {combined.shape}")
print(f"\nCategory distribution:\n{combined['category'].value_counts()}")

combined.to_parquet(f"{OUT_DIR}/combined.parquet", index=False)
print(f"\nSaved to {OUT_DIR}/combined.parquet")
