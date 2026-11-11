"""CSV and OFX/QFX Exports: read, then imported like a PDF Statement."""

from datetime import date

import pytest

from backend.statement_import import NeedsAccount, NeedsPeriod, import_statement, read_export
from tests.test_statement_import import add_account, rows

JANUARY = (date(2026, 1, 1), date(2026, 1, 31))


def csv(*lines):
    return read_export("\n".join(lines).encode(), "card.csv")


def test_csv_rows_and_rejected_lines():
    export = csv(
        "Transaction Date,Post Date,Description,Amount",
        '01/05/2026,01/06/2026,"TRADER JOE\'S, #552",-23.45',
        '2026-01-07,2026-01-08,AMAZON MKTP,"(1,200.00)"',
        "bad,,ROW,1.00",
        "01/09/2026,,NO AMOUNT,",
    )
    assert [(r.date, r.description, r.cents, r.negative) for r in export.rows] == [
        (date(2026, 1, 5), "TRADER JOE'S, #552", 2345, True),
        (date(2026, 1, 7), "AMAZON MKTP", 120000, True),
    ]
    assert [r["reason"] for r in export.rejected] == ["unrecognised date: 'bad'", "no amount"]
    assert export.last_four is None and export.period is None


def test_csv_with_a_byte_order_mark_and_missing_columns():
    assert len(read_export("﻿Date,Description,Amount\n2026-01-02,X,1.00".encode(), "a.csv").rows) == 1
    with pytest.raises(ValueError, match="needs date, description and amount"):
        csv("Date,Amount", "2026-01-02,1.00")


@pytest.mark.parametrize("purchase, payment", [("-12.00", "500.00"), ("12.00", "-500.00")])
def test_credit_card_csv_takes_the_common_sign_as_purchases(conn, purchase, payment):
    """Chase writes Purchases as negative, Amex and Discover as positive."""
    account_id = add_account(conn)
    export = csv(
        "Date,Description,Amount",
        f"2026-01-03,COFFEE,{purchase}",
        f"2026-01-04,LUNCH,{purchase}",
        f"2026-01-20,AUTOMATIC PAYMENT - THANK YOU,{payment}",
    )
    import_statement(conn, export, account_id=account_id, period=JANUARY)
    assert [(r["description"], r["direction"], r["kind"]) for r in rows(conn)] == [
        ("COFFEE", "out", "purchase"),
        ("LUNCH", "out", "purchase"),
        ("AUTOMATIC PAYMENT - THANK YOU", "in", "internal_transfer"),
    ]


def test_bank_csv_with_debit_and_credit_columns(conn):
    account_id = add_account(conn, kind="bank", last_four="9999")
    export = csv(
        "Date,Description,Debit,Credit",
        "2026-01-03,GROCERY STORE,54.10,",
        "2026-01-15,ACME CORP PAYROLL,,2000.00",
    )
    import_statement(conn, export, account_id=account_id, period=JANUARY)
    assert [(r["direction"], r["kind"]) for r in rows(conn)] == [("out", "purchase"), ("in", "income")]


def test_csv_asks_for_account_then_period(conn):
    account_id = add_account(conn)
    export = csv("Date,Description,Amount", "2026-01-03,COFFEE,4.50")
    with pytest.raises(NeedsAccount):
        import_statement(conn, export)
    with pytest.raises(NeedsPeriod):
        import_statement(conn, export, account_id=account_id)


def test_rows_outside_the_period_are_rejected_not_stored(conn):
    account_id = add_account(conn)
    export = csv("Date,Description,Amount", "2026-01-03,COFFEE,4.50", "2026-03-10,LATER,9.00")
    result = import_statement(conn, export, account_id=account_id, period=JANUARY)
    assert result.imported == 1
    assert result.rejected == [{"line": "2026-03-10,LATER,9.00", "reason": "date 2026-03-10 is outside the billing period"}]


OFX = """OFXHEADER:100
DATA:OFXSGML
<OFX><SIGNONMSGSRSV1><SONRS><FI><ORG>Chase Bank<FID>10898</FI></SONRS></SIGNONMSGSRSV1>
<CREDITCARDMSGSRSV1><CCSTMTTRNRS><CCSTMTRS><CURDEF>USD
<CCACCTFROM><ACCTID>4111222233331234</CCACCTFROM>
<BANKTRANLIST><DTSTART>20260101<DTEND>20260131
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260106120000<DTUSER>20260105<TRNAMT>-42.50<NAME>TRADER JOES</STMTTRN>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260109<TRNAMT>10.00<NAME>TRADER JOES</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>2026<TRNAMT>-1.00<NAME>BROKEN</STMTTRN>
</BANKTRANLIST></CCSTMTRS></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"""


def test_ofx_names_its_account_and_period():
    export = read_export(OFX.encode(), "card.qfx")
    assert (export.bank, export.last_four, export.period) == ("chase", "1234", JANUARY)
    assert [(r.date, r.cents, r.negative) for r in export.rows] == [
        (date(2026, 1, 5), 4250, True),   # the date it happened, not the date it posted
        (date(2026, 1, 9), 1000, False),
    ]
    assert len(export.rejected) == 1


def test_ofx_imports_without_asking_and_negative_is_money_out(conn):
    add_account(conn)
    result = import_statement(conn, read_export(OFX.encode(), "card.ofx"))
    assert (result.period_start, result.period_end) == JANUARY
    assert [(r["direction"], r["kind"]) for r in rows(conn)] == [("out", "purchase"), ("in", "refund")]


def test_a_file_that_is_not_ofx_is_refused():
    with pytest.raises(ValueError):
        read_export(b"hello", "card.ofx")
