import sqlite3

from backend.config import APP_DATA, DB_PATH, move_finance_data
from backend.vocabulary import ACCOUNT_KINDS, CATEGORIZED_KINDS, FALLBACK_CATEGORY, KINDS, sql_list

SCHEMA_VERSION = 4

_KIND_CHECK = sql_list(KINDS)


def get_connection() -> sqlite3.Connection:
    move_finance_data()
    APP_DATA.mkdir(parents=True, exist_ok=True)
    return connect(DB_PATH)


def connect(path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:  # v1: credit cards only, debit/credit
        _set_aside_v1_tables(conn)
    conn.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            kind        TEXT NOT NULL CHECK(kind IN ({sql_list(ACCOUNT_KINDS)})),
            bank        TEXT NOT NULL,
            last_four   TEXT,
            color       TEXT DEFAULT '#6366f1',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS statements (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id   INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            period_start TEXT NOT NULL,
            period_end   TEXT NOT NULL,
            file_name    TEXT,
            imported_at  TEXT DEFAULT (datetime('now')),
            UNIQUE (account_id, period_start, period_end)
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            statement_id         INTEGER NOT NULL REFERENCES statements(id) ON DELETE CASCADE,
            account_id           INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            date                 TEXT NOT NULL,
            description          TEXT NOT NULL,
            amount_cents         INTEGER NOT NULL CHECK(amount_cents >= 0),
            direction            TEXT NOT NULL CHECK(direction IN ('in', 'out')),
            kind                 TEXT NOT NULL CHECK(kind IN ({_KIND_CHECK})),
            category             TEXT,
            category_confidence  REAL,
            override_kind        TEXT CHECK(override_kind IN ({_KIND_CHECK})),
            override_category    TEXT
        );

        -- A Budget applies from its month until the next change for its Category;
        -- a NULL amount ends it. (v3)
        CREATE TABLE IF NOT EXISTS budgets (
            category      TEXT NOT NULL,
            from_month    TEXT NOT NULL CHECK(from_month GLOB '[0-9][0-9][0-9][0-9]-[0-1][0-9]'),
            amount_cents  INTEGER CHECK(amount_cents > 0),
            PRIMARY KEY (category, from_month)
        );

        -- Sharing (v4): docs/adr/0007.
        CREATE TABLE IF NOT EXISTS people (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(trim(name) != ''),
            note        TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS groups (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(trim(name) != ''),
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS group_members (
            group_id   INTEGER NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
            person_id  INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
            PRIMARY KEY (group_id, person_id)
        );

        -- paid_by NULL means the user paid. A Shared Expense the user paid counts
        -- once Linked to the Purchase that paid it, or when marked standalone
        -- (paid outside the tracked Accounts).
        CREATE TABLE IF NOT EXISTS shared_expenses (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            date              TEXT NOT NULL,
            description       TEXT NOT NULL,
            category          TEXT NOT NULL,
            total_cents       INTEGER NOT NULL CHECK(total_cents > 0),
            your_share_cents  INTEGER NOT NULL CHECK(your_share_cents >= 0),
            paid_by           INTEGER REFERENCES people(id) ON DELETE RESTRICT,
            group_id          INTEGER REFERENCES groups(id) ON DELETE SET NULL,
            transaction_id    INTEGER UNIQUE REFERENCES transactions(id) ON DELETE SET NULL,
            standalone        INTEGER NOT NULL DEFAULT 0 CHECK(standalone IN (0, 1)),
            source_key        TEXT UNIQUE,
            created_at        TEXT DEFAULT (datetime('now')),
            CHECK(your_share_cents <= total_cents),
            CHECK(paid_by IS NULL OR (transaction_id IS NULL AND standalone = 0))
        );

        -- Other People's Shares of an expense the user paid: what they owe the user.
        CREATE TABLE IF NOT EXISTS shares (
            expense_id  INTEGER NOT NULL REFERENCES shared_expenses(id) ON DELETE CASCADE,
            person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
            cents       INTEGER NOT NULL CHECK(cents > 0),
            PRIMARY KEY (expense_id, person_id)
        );

        CREATE TABLE IF NOT EXISTS settlements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT NOT NULL,
            person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE RESTRICT,
            cents       INTEGER NOT NULL CHECK(cents > 0),
            direction   TEXT NOT NULL CHECK(direction IN ('to_them', 'from_them')),
            note        TEXT,
            source_key  TEXT UNIQUE,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS ix_shared_expenses_date ON shared_expenses(date);

        CREATE INDEX IF NOT EXISTS ix_transactions_account   ON transactions(account_id);
        CREATE INDEX IF NOT EXISTS ix_transactions_statement ON transactions(statement_id);
        CREATE INDEX IF NOT EXISTS ix_transactions_date      ON transactions(date);

        -- The one definition of a Transaction's effective kind and Category:
        -- an Override wins over what import decided. Only categorized kinds
        -- have a Category. Recreated on every start so it follows vocabulary.py.
        DROP VIEW IF EXISTS transaction_view;
        CREATE VIEW transaction_view AS
        SELECT t.*,
               COALESCE(t.override_kind, t.kind) AS effective_kind,
               CASE WHEN COALESCE(t.override_kind, t.kind) IN ({sql_list(CATEGORIZED_KINDS)})
                    THEN COALESCE(t.override_category, t.category, '{FALLBACK_CATEGORY}')
               END AS effective_category,
               (t.override_kind IS NOT NULL OR t.override_category IS NOT NULL) AS overridden
        FROM transactions t;

        -- The one definition of what counts as Spending (docs/adr/0007): every
        -- Purchase and Refund, except that a Linked Purchase counts as the
        -- user's Share; plus the user's Share of Shared Expenses someone else
        -- paid or that were paid outside the tracked Accounts.
        DROP VIEW IF EXISTS spending_items;
        CREATE VIEW spending_items AS
        SELECT t.date, t.effective_category AS category,
               CASE WHEN e.id IS NOT NULL THEN e.your_share_cents
                    WHEN t.effective_kind = 'purchase' THEN t.amount_cents
                    ELSE -t.amount_cents END AS cents,
               t.id AS transaction_id, e.id AS expense_id
        FROM transaction_view t
        LEFT JOIN shared_expenses e ON e.transaction_id = t.id AND t.effective_kind = 'purchase'
        WHERE t.effective_kind IN ({sql_list(CATEGORIZED_KINDS)})
        UNION ALL
        SELECT e.date, e.category, e.your_share_cents, NULL, e.id
        FROM shared_expenses e
        WHERE e.transaction_id IS NULL AND (e.paid_by IS NOT NULL OR e.standalone = 1);

        PRAGMA user_version = {SCHEMA_VERSION};
        """
    )
    conn.execute("PRAGMA journal_mode = WAL")
    conn.commit()


def _set_aside_v1_tables(conn: sqlite3.Connection) -> None:
    """The v1 schema (credit cards only, debit/credit) can't be converted
    faithfully, so tables holding data are renamed to legacy_* rather than
    deleted; empty ones are dropped."""
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # Children first, so dropping a parent never trips a foreign key.
    for name in ("transactions", "imported_statements", "accounts"):
        if name not in tables:
            continue
        if conn.execute(f"SELECT EXISTS (SELECT 1 FROM {name})").fetchone()[0]:
            conn.execute(f"ALTER TABLE {name} RENAME TO legacy_{name}")
        else:
            conn.execute(f"DROP TABLE {name}")
    for (index,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_tx_%'"
    ).fetchall():
        conn.execute(f"DROP INDEX {index}")
