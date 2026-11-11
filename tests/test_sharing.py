"""Shared Expenses: what counts as Spending (docs/adr/0007), Balances, Links."""

from datetime import date

import pytest

from backend import ledger, sharing
from backend.ledger import LedgerError
from backend.sharing import NewExpense
from backend.statement_import import import_statement, read_export
from tests.test_statement_import import add_account

NOVEMBER = (date(2026, 11, 1), date(2026, 11, 30))


def card_with(conn, *lines):
    account_id = add_account(conn)
    csv = "\n".join(["Date,Description,Amount", *lines]).encode()
    import_statement(conn, read_export(csv, "nov.csv"), account_id=account_id, period=NOVEMBER)
    return account_id


def tx_id(conn, description):
    return conn.execute("SELECT id FROM transactions WHERE description = ?", (description,)).fetchone()[0]


def dining(conn):
    return ledger.spending(conn, "2026-11").by_category.get("Dining", 0)


@pytest.fixture
def friends(conn):
    return sharing.add_person(conn, "Alex"), sharing.add_person(conn, "Priya")


def dinner(alex, priya, **kw):
    """$90, split three ways, the user paid."""
    return NewExpense(date="2026-11-02", description="Dinner", category="Dining", total_cents=9000,
                      your_share_cents=3000, shares={alex: 3000, priya: 3000}, **kw)


def test_a_linked_purchase_counts_as_your_share(conn, friends):
    card_with(conn, "2026-11-02,OLIVE GARDEN,-90.00")
    conn.execute("UPDATE transactions SET override_category = 'Dining'")
    assert dining(conn) == 9000
    expense = sharing.add_expense(conn, dinner(*friends))
    assert dining(conn) == 9000  # not linked yet: the card Purchase counts, the expense doesn't
    sharing.link(conn, expense, tx_id(conn, "OLIVE GARDEN"))
    assert dining(conn) == 3000
    assert sharing.balances(conn) == {friends[0]: 3000, friends[1]: 3000}


def test_someone_elses_expense_counts_your_share(conn, friends):
    alex, _ = friends
    sharing.add_expense(conn, NewExpense(date="2026-11-05", description="Concert", category="Entertainment",
                                         total_cents=12000, your_share_cents=6000, paid_by=alex))
    assert ledger.spending(conn, "2026-11").by_category == {"Entertainment": 6000}
    assert sharing.balances(conn) == {alex: -6000}


def test_paid_outside_your_accounts_counts_once_marked(conn, friends):
    expense = sharing.add_expense(conn, dinner(*friends))
    assert dining(conn) == 0
    sharing.set_standalone(conn, expense, True)
    assert dining(conn) == 3000


def test_settlements_change_balances_not_spending(conn, friends):
    alex, priya = friends
    sharing.add_expense(conn, dinner(alex, priya, standalone=True))
    sharing.add_settlement(conn, date="2026-11-10", person_id=alex, cents=3000, direction="from_them")
    assert sharing.balances(conn) == {priya: 3000}
    sharing.settle_up(conn, priya, "2026-11-11")
    assert sharing.balances(conn) == {}
    assert dining(conn) == 3000


def test_shares_must_add_up_and_only_purchases_link(conn, friends):
    alex, priya = friends
    with pytest.raises(LedgerError, match="add up"):
        sharing.add_expense(conn, NewExpense(date="2026-11-02", description="Dinner", category="Dining",
                                             total_cents=9000, your_share_cents=3000, shares={alex: 3000}))
    with pytest.raises(LedgerError, match="you paid"):
        sharing.add_expense(conn, NewExpense(date="2026-11-02", description="Dinner", category="Dining",
                                             total_cents=9000, your_share_cents=3000, paid_by=alex, standalone=True))
    card_with(conn, "2026-11-03,COFFEE,-4.00", "2026-11-03,LUNCH,-12.00", "2026-11-04,AUTOMATIC PAYMENT - THANK YOU,500.00")
    expense = sharing.add_expense(conn, dinner(alex, priya))
    with pytest.raises(LedgerError, match="Only a Purchase"):
        sharing.link(conn, expense, tx_id(conn, "AUTOMATIC PAYMENT - THANK YOU"))


def test_links_survive_importing_the_statement_again(conn, friends):
    account_id = card_with(conn, "2026-11-02,OLIVE GARDEN,-90.00", "2026-11-03,COFFEE,-4.00")
    expense = sharing.add_expense(conn, dinner(*friends))
    sharing.link(conn, expense, tx_id(conn, "OLIVE GARDEN"))
    again = b"Date,Description,Amount\n2026-11-02,OLIVE GARDEN,-90.00\n2026-11-03,COFFEE,-4.00\n"
    import_statement(conn, read_export(again, "nov.csv"), account_id=account_id, period=NOVEMBER)
    [linked] = sharing.expenses(conn)
    assert linked["transaction"]["description"] == "OLIVE GARDEN" and linked["counted"]


def test_people_in_use_cant_be_removed(conn, friends):
    alex, _ = friends
    sharing.add_expense(conn, dinner(*friends))
    with pytest.raises(LedgerError, match="still used"):
        sharing.delete_person(conn, alex)
    with pytest.raises(LedgerError, match="already in People"):
        sharing.add_person(conn, "alex")


def test_suggestions_pair_expenses_with_purchases(conn, friends):
    card_with(conn, "2026-11-03,OLIVE GARDEN #123,-90.00", "2026-11-03,OTHER PLACE,-90.00", "2026-11-20,FAR AWAY,-90.00")
    expense = sharing.add_expense(conn, NewExpense(
        date="2026-11-02", description="Olive Garden dinner", category="Dining", total_cents=9000,
        your_share_cents=3000, shares={friends[0]: 6000}))
    [best] = sharing.suggestions(conn)
    assert best["expense_id"] == expense and best["transaction"]["description"] == "OLIVE GARDEN #123"
    assert best["score"] >= 90


def test_groups_hold_people(conn, friends):
    group = sharing.add_group(conn, "Apartment", list(friends))
    assert [m["name"] for m in sharing.groups(conn)[0]["members"]] == ["Alex", "Priya"]
    sharing.remove_member(conn, group, friends[0])
    assert [m["name"] for m in sharing.groups(conn)[0]["members"]] == ["Priya"]
