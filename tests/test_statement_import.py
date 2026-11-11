from datetime import date

import pytest

from backend.prediction.base import OneAtATime
from backend.statement_import import (
    AccountMismatch,
    Document,
    NeedsAccount,
    NeedsPeriod,
    NoTransactions,
    Page,
    import_statement,
)


def add_account(conn, kind="credit_card", bank="chase", last_four="1234", name="Card"):
    cur = conn.execute(
        "INSERT INTO accounts (name, kind, bank, last_four) VALUES (?, ?, ?, ?)",
        (name, kind, bank, last_four),
    )
    conn.commit()
    return cur.lastrowid


def statement(*lines, header=None):
    header = header or [
        "Chase Freedom",
        "Account ending in 1234",
        "Opening/Closing Date 12/05/25 - 01/04/26",
    ]
    return Document("statement.pdf", [Page("\n".join([*header, *lines]))])


def rows(conn):
    return conn.execute(
        "SELECT date, description, amount_cents, direction, effective_kind AS kind,"
        " effective_category AS category FROM transaction_view ORDER BY id"
    ).fetchall()


# --- reading the Statement ----------------------------------------------------


def test_dates_without_a_year_take_it_from_the_billing_period(conn):
    add_account(conn)
    import_statement(conn, statement("12/28 WHOLE FOODS 54.20", "01/02 SHELL OIL 38.10"))
    assert [r["date"] for r in rows(conn)] == ["2025-12-28", "2026-01-02"]


def test_posting_date_is_ignored_in_favour_of_the_date_it_happened(conn):
    add_account(conn)
    import_statement(conn, statement("12/30 01/02 WHOLE FOODS 54.20"))
    assert rows(conn)[0]["date"] == "2025-12-30"


def test_amount_formats_and_the_running_balance_is_ignored(conn):
    add_account(conn)
    import_statement(conn, statement(
        "12/10 NORDSTROM (45.00)",
        "12/11 TARGET 1,234.56 2,000.00",
        "12/12 BEST BUY 10.00 CR",
    ))
    got = [(r["amount_cents"], r["direction"], r["kind"]) for r in rows(conn)]
    assert got == [(4500, "in", "refund"), (123456, "out", "purchase"), (1000, "in", "refund")]


def test_bad_rows_are_rejected_with_a_reason_not_stored(conn):
    add_account(conn)
    result = import_statement(conn, statement("12/10 COFFEE 4.50", "13/45 NONSENSE 9.99", "06/01 TOO EARLY 5.00"))
    assert result.imported == 1
    assert [r["reason"] for r in result.rejected] == [
        "not a real date: '13/45'",
        "date '06/01' is outside the billing period",
    ]


def test_rows_are_read_from_tables_too(conn):
    add_account(conn)
    doc = Document("s.pdf", [Page(
        "Chase\nAccount ending in 1234\nStatement period 12/05/25 to 01/04/26",
        tables=[[["Date", "Merchant", "Amount"], ["12/15", "UBER TRIP", "23.10"]]],
    )])
    import_statement(conn, doc)
    assert [(r["description"], r["amount_cents"]) for r in rows(conn)] == [("UBER TRIP", 2310)]


def test_a_statement_with_no_transactions_is_not_recorded(conn):
    add_account(conn)
    with pytest.raises(NoTransactions):
        import_statement(conn, statement("nothing here"))
    assert conn.execute("SELECT COUNT(*) FROM statements").fetchone()[0] == 0


# --- billing period and Account ------------------------------------------------


def test_missing_period_asks_for_it_then_imports(conn):
    add_account(conn)
    doc = statement("12/10 COFFEE 4.50", header=["Chase", "Account ending in 1234"])
    with pytest.raises(NeedsPeriod):
        import_statement(conn, doc)
    result = import_statement(conn, doc, period=(date(2025, 12, 5), date(2026, 1, 4)))
    assert result.imported == 1


def test_account_is_matched_from_last_four(conn):
    add_account(conn, last_four="9999", name="Other card")
    target = add_account(conn, last_four="1234")
    assert import_statement(conn, statement("12/10 COFFEE 4.50")).account_id == target


def test_account_must_be_chosen_when_it_cant_be_matched(conn):
    add_account(conn, last_four="9999")
    with pytest.raises(NeedsAccount):
        import_statement(conn, statement("12/10 COFFEE 4.50"))


def test_statement_for_a_different_account_is_stopped(conn):
    other = add_account(conn, last_four="9999", name="Sapphire")
    with pytest.raises(AccountMismatch, match="ending in 1234"):
        import_statement(conn, statement("12/10 COFFEE 4.50"), account_id=other)
    amex = add_account(conn, bank="amex", last_four=None, name="Amex")
    with pytest.raises(AccountMismatch, match="Chase Statement"):
        import_statement(conn, statement("12/10 COFFEE 4.50"), account_id=amex)


# --- replacing a Statement ----------------------------------------------------


def test_reimport_replaces_and_carries_overrides_over(conn):
    add_account(conn)
    import_statement(conn, statement("12/10 COFFEE 4.50", "12/10 COFFEE 4.50", "12/11 GIFT SHOP 20.00"))
    ids = [r[0] for r in conn.execute("SELECT id FROM transactions ORDER BY id")]
    conn.execute("UPDATE transactions SET override_category = 'Dining' WHERE id = ?", (ids[0],))
    conn.execute("UPDATE transactions SET override_category = 'Kids & Pets' WHERE id = ?", (ids[2],))
    conn.commit()

    # The parser now reads the gift shop line differently, so its Override can't follow.
    result = import_statement(conn, statement("12/10 COFFEE 4.50", "12/10 COFFEE 4.50", "12/11 GIFT SHOP INC 20.00"))

    assert result.replaced
    assert conn.execute("SELECT COUNT(*) FROM statements").fetchone()[0] == 1
    assert [r["category"] for r in rows(conn)] == ["Dining", "Other", "Other"]
    assert [(u.description, u.override_category) for u in result.unmatched_overrides] == [
        ("GIFT SHOP", "Kids & Pets")
    ]


# --- kinds ----------------------------------------------------------------------


def kinds_for(conn, lines, account_kind, also_track=None):
    if also_track:
        add_account(conn, kind=also_track, bank="other", last_four="0000", name="other")
    add_account(conn, kind=account_kind)
    import_statement(conn, statement(*lines))
    return [r["kind"] for r in rows(conn)]


def test_credit_card_kinds(conn):
    assert kinds_for(conn, [
        "12/10 AMAZON 30.00",
        "12/11 AMAZON -30.00",
        "12/12 PAYMENT THANK YOU -500.00",
        "12/13 REWARDS REDEMPTION -25.00",
        "12/14 ATM CASH ADVANCE 100.00",
    ], "credit_card") == ["purchase", "refund", "internal_transfer", "reward", "withdrawal"]


def test_card_payment_is_internal_even_when_the_bank_account_is_not_tracked(conn):
    assert kinds_for(conn, ["12/12 PAYMENT THANK YOU -500.00"], "credit_card") == ["internal_transfer"]


def test_card_payoff_from_bank_is_internal_even_when_the_card_is_not_tracked(conn):
    assert kinds_for(conn, ["12/15 CHASE CREDIT CRD AUTOPAY -500.00"], "bank") == ["internal_transfer"]


def test_bank_kinds(conn):
    assert kinds_for(conn, [
        "12/10 STARBUCKS -4.50",
        "12/11 ATM WITHDRAWAL 1 MAIN ST -60.00",
        "12/11 ATM FEE -3.00",
        "12/12 ZELLE TO JANE -40.00",
        "12/13 ZELLE FROM JOHN 30.00",
        "12/14 ACME PAYROLL DIRECT DEP 2,000.00",
        "12/15 CHASE CREDIT CRD AUTOPAY -500.00",
        "12/16 AMAZON REFUND 12.00",
    ], "bank", also_track="credit_card") == [
        "purchase", "withdrawal", "purchase", "peer_transfer", "peer_transfer",
        "income", "internal_transfer", "refund",
    ]


class Recorder(OneAtATime):
    """A CategoryPredictor that answers Transport and records what it was asked."""

    def __init__(self):
        self.asked = []

    def predict(self, description, amount_cents, kind, when):
        self.asked.append((description, amount_cents, kind, when))
        return "Transport", 0.9


def test_only_purchases_and_refunds_are_predicted(conn):
    predictor = Recorder()
    add_account(conn)
    import_statement(
        conn,
        statement("12/10 SHELL 30.00", "12/11 SHELL -30.00", "12/12 PAYMENT THANK YOU -500.00"),
        predictor=predictor,
    )
    assert [r["category"] for r in rows(conn)] == ["Transport", "Transport", None]
    # The predictor sees the kind, so a Refund isn't mistaken for a Purchase.
    assert predictor.asked == [
        ("SHELL", 3000, "purchase", date(2025, 12, 10)),
        ("SHELL", 3000, "refund", date(2025, 12, 11)),
    ]


def test_without_a_model_categories_default_to_other(conn):
    add_account(conn)
    import_statement(conn, statement("12/10 SHELL 30.00"))
    assert tuple(conn.execute("SELECT category, category_confidence FROM transactions").fetchone()) == ("Other", None)


def test_table_rows_take_the_amount_not_the_running_balance(conn):
    add_account(conn, kind="bank")
    table = [
        ["Date", "Description", "Amount", "Balance"],
        ["12/10", "STARBUCKS", "-4.50", "1,995.50"],
        ["12/14", "ACME PAYROLL", "2,000.00", "3,995.50"],
    ]
    header = "Chase Checking\nAccount ending in 1234\nStatement Period 12/05/25 - 01/04/26"
    import_statement(conn, Document("s.pdf", [Page(header, tables=[table])]))
    assert [(r["description"], r["amount_cents"], r["direction"]) for r in rows(conn)] == [
        ("STARBUCKS", 450, "out"),
        ("ACME PAYROLL", 200000, "in"),
    ]


@pytest.mark.parametrize("text", ["4.50", "-4.50", "(4.50)", "4.50-", "4.50 CR", "$1,234.56", "-$4.50", "+4.50"])
def test_every_amount_a_row_can_hold_is_parsed(text):
    from backend.statement_import.reading import _CELL_AMOUNT, _parse_amount

    assert _CELL_AMOUNT.match(text)
    assert _parse_amount(text)[0] > 0
