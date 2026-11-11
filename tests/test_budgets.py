"""Budgets: set from a month on, carried forward until changed."""

import pytest

from backend import ledger
from backend.ledger import LedgerError, budgets, set_budget


def test_a_budget_carries_forward_until_changed(conn):
    set_budget(conn, "Dining", "2026-01", 30000)
    assert budgets(conn, "2025-12") == {}
    assert budgets(conn, "2026-01") == budgets(conn, "2026-06") == {"Dining": 30000}

    set_budget(conn, "Dining", "2026-03", 20000)
    assert budgets(conn, "2026-02") == {"Dining": 30000}  # earlier months keep theirs
    assert budgets(conn, "2026-03") == budgets(conn, "2027-01") == {"Dining": 20000}


def test_clearing_a_budget_ends_it_from_that_month(conn):
    set_budget(conn, "Groceries", "2026-01", 50000)
    set_budget(conn, "Groceries", "2026-04", None)
    assert budgets(conn, "2026-03") == {"Groceries": 50000}
    assert budgets(conn, "2026-04") == {}


def test_setting_the_same_amount_again_adds_nothing(conn):
    set_budget(conn, "Dining", "2026-01", 30000)
    set_budget(conn, "Dining", "2026-02", 25000)
    set_budget(conn, "Dining", "2026-02", 30000)  # changed back: February follows January
    assert conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 1
    set_budget(conn, "Travel", "2026-01", None)  # clearing what was never set
    assert conn.execute("SELECT COUNT(*) FROM budgets").fetchone()[0] == 1


@pytest.mark.parametrize("category, month, cents", [
    ("Not a category", "2026-01", 100),
    ("Dining", "2026-13", 100),
    ("Dining", "January", 100),
    ("Dining", "2026-01", 0),
    ("Dining", "2026-01", -5),
])
def test_bad_budgets_are_refused(conn, category, month, cents):
    with pytest.raises(LedgerError):
        set_budget(conn, category, month, cents)
