import pytest

from backend import ledger
from backend.statement_import import Document, Page, import_statement


def card_statement(*lines):
    header = ["Chase Freedom", "Account ending in 1234", "Opening/Closing Date 12/05/25 - 01/04/26"]
    return Document("s.pdf", [Page("\n".join([*header, *lines]))])


@pytest.fixture
def card(conn):
    return ledger.add_account(conn, name="Card", kind="credit_card", bank="chase", last_four="1234")


def tx_id(conn, description):
    return conn.execute("SELECT id FROM transactions WHERE description = ?", (description,)).fetchone()[0]


def test_spending_is_purchases_minus_refunds_by_category_and_month(conn, card):
    import_statement(conn, card_statement(
        "12/10 SHOES 100.00",
        "12/20 SHOES -40.00",
        "12/21 PAYMENT THANK YOU -500.00",
        "12/22 ATM CASH ADVANCE 60.00",
        "01/02 LUNCH 12.00",
    ))
    december = ledger.spending(conn, "2025-12")
    assert december.by_category == {"Other": 6000}
    assert december.withdrawn_cents == 6000
    assert ledger.spending(conn, "2026-01").by_category == {"Other": 1200}


def test_a_category_can_go_negative_when_refunds_exceed_purchases(conn, card):
    import_statement(conn, card_statement("12/10 SHOES 10.00", "12/20 SHOES RETURN -40.00"))
    assert ledger.spending(conn, "2025-12").by_category == {"Other": -3000}


def test_overrides_change_spending(conn, card):
    import_statement(conn, card_statement("12/10 RENT CO 1,500.00", "12/11 SHOES 50.00"))
    ledger.set_override(conn, tx_id(conn, "RENT CO"), kind=None, category="Housing")
    assert ledger.spending(conn, "2025-12").by_category == {"Housing": 150000, "Other": 5000}

    ledger.set_override(conn, tx_id(conn, "SHOES"), kind="peer_transfer", category=None)
    assert ledger.spending(conn, "2025-12").by_category == {"Housing": 150000}


def test_override_validation(conn, card):
    import_statement(conn, card_statement("12/10 SHOES 50.00"))
    with pytest.raises(ledger.LedgerError, match="Unknown kind"):
        ledger.set_override(conn, tx_id(conn, "SHOES"), kind="gift", category=None)
    with pytest.raises(ledger.LedgerError, match="Unknown Category"):
        ledger.set_override(conn, tx_id(conn, "SHOES"), kind=None, category="Gas")
    with pytest.raises(ledger.NotFound):
        ledger.set_override(conn, 999, kind=None, category=None)


class Fixed:
    def predict(self, description, amount_cents, kind, when):
        return "Housing", 0.8


def test_making_a_transfer_a_purchase_predicts_its_category(conn):
    ledger.add_account(conn, name="Checking", kind="bank", bank="chase", last_four="1234")
    import_statement(conn, card_statement("12/10 ZELLE TO LANDLORD -1,500.00"))
    rent = tx_id(conn, "ZELLE TO LANDLORD")

    ledger.set_override(conn, rent, kind="purchase", category=None, predictor=Fixed())

    [tx] = ledger.transactions(conn)
    assert (tx["kind"], tx["category"], tx["category_confidence"]) == ("purchase", "Housing", 0.8)


def test_transaction_filters(conn, card):
    import_statement(conn, card_statement("12/10 SHOES 50.00", "12/12 PAYMENT THANK YOU -500.00", "01/02 LUNCH 12.00"))
    assert [t["description"] for t in ledger.transactions(conn, ledger.TransactionFilter(month="2025-12"))] == [
        "PAYMENT THANK YOU", "SHOES"]
    assert [t["description"] for t in ledger.transactions(conn, ledger.TransactionFilter(kind="internal_transfer"))] == [
        "PAYMENT THANK YOU"]
    assert ledger.transactions(conn, ledger.TransactionFilter(account_id=card + 1)) == []


def test_corrections_are_hand_set_categories_of_categorized_transactions(conn, card):
    import_statement(conn, card_statement("12/10 RENT CO 1,500.00", "12/11 SHOES 50.00", "12/12 PAYMENT THANK YOU -500.00"))
    ledger.set_override(conn, tx_id(conn, "RENT CO"), kind=None, category="Housing")
    ledger.set_override(conn, tx_id(conn, "SHOES"), kind="peer_transfer", category="Shopping")
    assert ledger.corrections(conn) == [
        {"description": "RENT CO", "amount_cents": 150000, "kind": "purchase", "date": "2025-12-10", "category": "Housing"}
    ]


def test_unknown_account_kind_is_refused(conn):
    with pytest.raises(ledger.LedgerError):
        ledger.add_account(conn, name="X", kind="debit_card", bank="chase")


def test_deleting_an_account_removes_its_transactions(conn, card):
    import_statement(conn, card_statement("12/10 SHOES 50.00"))
    ledger.delete_account(conn, card)
    assert ledger.transactions(conn) == []
