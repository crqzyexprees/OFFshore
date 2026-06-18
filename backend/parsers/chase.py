import pdfplumber

from backend.parsers.base import Transaction, clean_amount, normalize_date


def parse(pdf_path: str) -> list[Transaction]:
    transactions = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    date_raw = row[0] or ""
                    desc_raw = row[1] or ""
                    amt_raw = row[-1] or ""
                    if not date_raw.strip() or not amt_raw.strip():
                        continue
                    try:
                        amt = clean_amount(amt_raw)
                        transactions.append(
                            Transaction(
                                date=normalize_date(date_raw.strip()),
                                description=desc_raw.strip(),
                                amount=abs(amt),
                                tx_type="credit" if amt < 0 else "debit",
                            )
                        )
                    except Exception:
                        continue
    return transactions
