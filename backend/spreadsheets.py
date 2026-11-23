"""Spreadsheet copy: all the data as CSV files in one zip, for reading and
for other tools. Unlike a Backup it can't be restored; money is in dollars, and each file uses the same definitions the app shows (Spending
from `spending_items`, Balances from Settlements and Shares).
"""

import csv
import io
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from backend import ledger, sharing
from backend.backup import write_private


def dollars(cents: int | None) -> str:
    if cents is None:
        return ""
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def tables(conn: sqlite3.Connection) -> dict[str, list[list]]:
    """Each file's rows, header first."""
    accounts = {a["id"]: a["name"] for a in ledger.accounts(conn)}
    expenses = sharing.expenses(conn)
    shared_by_tx = {e["transaction"]["id"]: e["description"] for e in expenses if e["transaction"]}

    return {
        "accounts.csv": [["Account", "Kind", "Bank", "Last four"]] + [
            [a["name"], a["kind"], a["bank"], a["last_four"] or ""] for a in ledger.accounts(conn)
        ],
        "statements.csv": [["Account", "Period start", "Period end", "File", "Transactions"]] + [
            [accounts.get(s["account_id"], ""), s["period_start"], s["period_end"], s["file_name"] or "",
             s["transactions"]]
            for s in ledger.statements(conn)
        ],
        "transactions.csv": [["Date", "Account", "Description", "Amount", "Money", "Kind", "Category",
                              "Edited by you", "Pays for shared expense"]] + [
            [t["date"], accounts.get(t["account_id"], ""), t["description"], dollars(t["amount_cents"]),
             t["direction"], t["kind"], t["category"] or "", "yes" if t["overridden"] else "",
             shared_by_tx.get(t["id"], "")]
            for t in reversed(ledger.transactions(conn))
        ],
        "spending.csv": [["Date", "Category", "Amount", "From"]] + [
            [r["date"], r["category"], dollars(r["cents"]), r["source"]]
            for r in conn.execute(
                """SELECT i.date, i.category, i.cents,
                          COALESCE(t.description, e.description) AS source
                   FROM spending_items i
                   LEFT JOIN transactions t ON t.id = i.transaction_id
                   LEFT JOIN shared_expenses e ON e.id = i.expense_id
                   ORDER BY i.date"""
            )
        ],
        "shared_expenses.csv": [["Date", "Description", "Category", "Total", "Your share", "Paid by",
                                 "Others' shares", "Group", "Card charge", "Counts as spending"]] + [
            [e["date"], e["description"], e["category"], dollars(e["total_cents"]),
             dollars(e["your_share_cents"]), e["paid_by_name"] or "You",
             "; ".join(f"{s['name']} {dollars(s['cents'])}" for s in e["shares"]),
             e["group_name"] or "",
             e["transaction"]["description"] if e["transaction"] else ("paid outside your accounts" if e["standalone"] else ""),
             "yes" if e["counted"] else "no"]
            for e in reversed(expenses)
        ],
        "settlements.csv": [["Date", "Person", "Who paid", "Amount", "Note"]] + [
            [s["date"], s["name"], f"{s['name']} paid you" if s["direction"] == "from_them" else f"You paid {s['name']}",
             dollars(s["cents"]), s["note"] or ""]
            for s in reversed(sharing.settlements(conn))
        ],
        "people.csv": [["Name", "Note", "Owes you (negative: you owe them)"]] + [
            [p["name"], p["note"] or "", dollars(p["balance_cents"])] for p in sharing.people(conn)
        ],
        "groups.csv": [["Group", "Members"]] + [
            [g["name"], "; ".join(m["name"] for m in g["members"])] for g in sharing.groups(conn)
        ],
        "budgets.csv": [["Category", "From month", "Amount (blank: ended)"]] + [
            [r["category"], r["from_month"], dollars(r["amount_cents"])]
            for r in conn.execute("SELECT category, from_month, amount_cents FROM budgets ORDER BY category, from_month")
        ],
    }


def spreadsheet_zip(conn: sqlite3.Connection) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, rows in tables(conn).items():
            text = io.StringIO()
            csv.writer(text).writerows(rows)
            # A byte-order mark so spreadsheet apps read the file as UTF-8.
            z.writestr(name, "﻿" + text.getvalue())
    return buffer.getvalue()


def save_spreadsheets(conn: sqlite3.Connection, directory: Path) -> Path:
    """Writes the zip, readable only by its owner, and returns where."""
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    path = directory / f"splitlens-spreadsheets-{stamp}.zip"
    n = 1
    while path.exists():
        n += 1
        path = directory / f"splitlens-spreadsheets-{stamp}-{n}.zip"
    write_private(path, spreadsheet_zip(conn))
    return path
