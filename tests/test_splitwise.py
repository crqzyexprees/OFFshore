"""Splitwise exports: nets turned into Shares, Settlements, and safe re-imports."""

import pytest

from backend import ledger, sharing
from backend.splitwise import SplitwiseError, import_splitwise, read_splitwise

EXPORT = b"""Date,Description,Category,Cost,Currency,Sam,Alex,Priya
2026-11-02,Dinner,Dining out,90.00,USD,60.00,-30.00,-30.00
2026-11-05,Concert,Movies,120.00,USD,-60.00,60.00,0.00
2026-11-06,Cab home,Taxi,30.00,USD,0.00,15.00,-15.00
2026-11-07,Hotel,Hotel,300.00,USD,50.00,100.00,-150.00
2026-11-08,Ramen,Dining out,20.00,EUR,10.00,-10.00,0.00
2026-11-09,Alex paid Sam,Payment,30.00,USD,-30.00,30.00,0.00
2026-11-09,Dinner,Dining out,90.00,USD,60.00,-30.00,-30.00

2026-11-30,Total balance,,,USD,10.00,-10.00,0.00
"""


def people(conn):
    return {p["name"]: p["id"] for p in sharing.people(conn)}


def test_nets_become_the_right_shares(conn):
    result = import_splitwise(conn, read_splitwise(EXPORT), your_name="Sam", group_name="Trip")
    assert (result.imported, result.settlements, result.not_involving_you) == (3, 1, 1)
    assert [s["reason"] for s in result.skipped] == [
        "several people paid, so your share can't be worked out; add it by hand",
        "in EUR; only US dollars are tracked",
    ]
    by_date = {e["date"]: e for e in sharing.expenses(conn)}
    dinner = by_date["2026-11-02"]
    # The payer's net is +60, but their Share is 90 - 60 = 30 (the old app read 60).
    assert (dinner["your_share_cents"], dinner["paid_by"], dinner["category"]) == (3000, None, "Dining")
    assert {s["name"]: s["cents"] for s in dinner["shares"]} == {"Alex": 3000, "Priya": 3000}
    concert = by_date["2026-11-05"]
    assert (concert["your_share_cents"], concert["paid_by_name"], concert["category"]) == (6000, "Alex", "Entertainment")

    ids = people(conn)
    # Alex: owes 30 (dinner) + 30 (second dinner) - 60 (concert) - 30 paid back = -30
    assert sharing.balances(conn) == {ids["Alex"]: -3000, ids["Priya"]: 6000}
    assert [g["name"] for g in sharing.groups(conn)] == ["Trip"]
    # Only the concert counts yet: the dinners Sam paid wait for their card Purchase.
    assert ledger.spending(conn, "2026-11").by_category == {"Entertainment": 6000}


def test_importing_again_adds_only_new_rows(conn):
    import_splitwise(conn, read_splitwise(EXPORT), your_name="Sam")
    again = import_splitwise(conn, read_splitwise(EXPORT), your_name="Sam")
    assert (again.imported, again.settlements, again.already_imported) == (0, 0, 4)
    assert len(sharing.expenses(conn)) == 3


def test_you_must_be_a_member(conn):
    with pytest.raises(SplitwiseError, match="Choose which member is you"):
        import_splitwise(conn, read_splitwise(EXPORT), your_name="Nobody")


def test_files_that_are_not_splitwise_exports(conn):
    with pytest.raises(SplitwiseError, match="Date, Description and Cost"):
        read_splitwise(b"Date,Description,Amount\n2026-11-02,X,1.00\n")
    with pytest.raises(SplitwiseError, match="no member columns"):
        read_splitwise(b"Date,Description,Category,Cost,Currency\n2026-11-02,X,General,1.00,USD\n")
