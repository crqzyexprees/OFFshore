import sqlite3
from pathlib import Path

from backend.config import APP_DATA, DB_PATH


def get_connection() -> sqlite3.Connection:
    APP_DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;

        CREATE TABLE IF NOT EXISTS accounts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            bank        TEXT NOT NULL,
            last_four   TEXT,
            color       TEXT DEFAULT '#6366f1',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id           INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            date                 TEXT NOT NULL,
            description          TEXT NOT NULL,
            merchant             TEXT,
            amount               REAL NOT NULL,
            tx_type              TEXT CHECK(tx_type IN ('debit','credit')) DEFAULT 'debit',
            category             TEXT,
            category_confidence  REAL,
            manually_overridden  INTEGER DEFAULT 0,
            manual_category      TEXT,
            statement_hash       TEXT,
            created_at           TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS imported_statements (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id  INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            file_hash   TEXT NOT NULL UNIQUE,
            file_name   TEXT,
            tx_count    INTEGER DEFAULT 0,
            imported_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_tx_account ON transactions(account_id);
        CREATE INDEX IF NOT EXISTS idx_tx_date    ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_tx_cat     ON transactions(category);
        """
    )
    conn.commit()
