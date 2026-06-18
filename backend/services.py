from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backend.classifier import TxClassifier
from backend.db import get_connection
from backend.parsers import parse_statement


@dataclass
class ImportResult:
    imported: int
    duplicates: int
    failed: int
    bank: str


def import_pdf(
    pdf_path: str,
    account_id: int,
    classifier: Optional[TxClassifier],
) -> ImportResult:
    parsed = parse_statement(pdf_path)
    if parsed.get("error"):
        raise ValueError(parsed["error"])

    file_hash = parsed["file_hash"]
    bank = parsed["bank"]

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM imported_statements WHERE file_hash = ?",
            (file_hash,),
        ).fetchone()
        if row and row[0] > 0:
            return ImportResult(imported=0, duplicates=1, failed=0, bank=bank)

        imported = 0
        failed = 0

        for tx in parsed["transactions"]:
            description = tx.get("description", "")
            amount = float(tx.get("amount", 0))
            date = tx.get("date", "")
            tx_type = tx.get("tx_type", "debit")

            if not description or not date:
                failed += 1
                continue

            month = 6.0
            parts = date.split("-")
            if len(parts) > 1:
                try:
                    month = float(parts[1])
                except ValueError:
                    pass

            if classifier:
                category, confidence = classifier.classify(
                    description, amount, month=month
                )
            else:
                category, confidence = "Other", None

            conn.execute(
                """INSERT INTO transactions
                   (account_id, date, description, amount, tx_type,
                    category, category_confidence, statement_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    account_id,
                    date,
                    description,
                    amount,
                    tx_type,
                    category,
                    confidence,
                    file_hash,
                ),
            )
            imported += 1

        conn.execute(
            """INSERT OR IGNORE INTO imported_statements
               (account_id, file_hash, file_name, tx_count)
               VALUES (?, ?, ?, ?)""",
            (account_id, file_hash, parsed["file_name"], imported),
        )
        conn.commit()
        return ImportResult(imported=imported, duplicates=0, failed=failed, bank=bank)
    finally:
        conn.close()
