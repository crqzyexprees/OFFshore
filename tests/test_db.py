from backend.db import connect, init_db

V1_SCHEMA = """
CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT, bank TEXT);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(id), amount REAL);
CREATE TABLE imported_statements (id INTEGER PRIMARY KEY, file_hash TEXT);
CREATE INDEX idx_tx_account ON transactions(account_id);
"""


def tables(conn):
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_v1_data_is_set_aside_not_deleted():
    conn = connect(":memory:")
    conn.executescript(V1_SCHEMA + "INSERT INTO accounts VALUES (1, 'Old card', 'Chase');"
                       "INSERT INTO transactions VALUES (1, 1, 9.99);")
    init_db(conn)
    assert {"legacy_accounts", "legacy_transactions", "accounts", "statements"} <= tables(conn)
    assert "imported_statements" not in tables(conn)  # was empty, so dropped
    assert conn.execute("SELECT name FROM legacy_accounts").fetchone()[0] == "Old card"
    assert conn.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] == 0


def test_init_is_idempotent():
    conn = connect(":memory:")
    init_db(conn)
    init_db(conn)
    assert "legacy_accounts" not in tables(conn)
