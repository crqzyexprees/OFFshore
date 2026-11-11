"""Backups: saved, encrypted, and restored only when they're safe to restore."""

import os
import stat

import pytest

from backend import backup
from backend.backup import BackupError, restore_backup, save_backup
from backend.db import connect, init_db
from tests.test_statement_import import add_account


def names(conn):
    return [r[0] for r in conn.execute("SELECT name FROM accounts ORDER BY id")]


@pytest.fixture
def live(tmp_path):
    conn = connect(tmp_path / "live.db")
    init_db(conn)
    yield conn
    conn.close()


def test_plain_backup_round_trip_and_a_copy_of_what_was_there(live, tmp_path):
    add_account(live, name="Card")
    saved = save_backup(live, tmp_path / "backups")
    assert not saved.encrypted and saved.path.suffix == ".db"
    assert stat.S_IMODE(os.stat(saved.path).st_mode) == 0o600

    add_account(live, name="Added later", last_four="5555")
    previous = restore_backup(live, saved.path.read_bytes(), tmp_path / "safety")
    assert names(live) == ["Card"]

    with connect(previous) as before:
        assert names(before) == ["Card", "Added later"]


def test_encrypted_backup_needs_its_password(live, tmp_path):
    add_account(live, name="Secret card")
    saved = save_backup(live, tmp_path, password="correct horse")
    data = saved.path.read_bytes()
    assert saved.encrypted and data.startswith(backup.MAGIC)
    assert b"Secret card" not in data

    with pytest.raises(BackupError, match="encrypted"):
        restore_backup(live, data, tmp_path / "safety")
    with pytest.raises(BackupError, match="Wrong password"):
        restore_backup(live, data, tmp_path / "safety", password="wrong horse")
    assert not (tmp_path / "safety").exists()  # refused before anything was touched

    live.execute("DELETE FROM accounts")
    live.commit()
    restore_backup(live, data, tmp_path / "safety", password="correct horse")
    assert names(live) == ["Secret card"]


def test_short_passwords_are_refused(live, tmp_path):
    with pytest.raises(BackupError, match="at least 8"):
        save_backup(live, tmp_path, password="short")


def test_tampered_encrypted_backup_is_refused(live, tmp_path):
    data = bytearray(save_backup(live, tmp_path, password="correct horse").path.read_bytes())
    data[-1] ^= 1
    with pytest.raises(BackupError, match="Wrong password, or the Backup is damaged"):
        restore_backup(live, bytes(data), tmp_path / "safety", password="correct horse")


def test_files_that_are_not_splitlens_backups_are_refused(live, tmp_path):
    other = connect(tmp_path / "other.db")
    other.execute("CREATE TABLE notes (text TEXT)")
    other.execute("PRAGMA user_version = 2")
    other.commit()
    other.close()
    add_account(live, name="Kept")
    for data in (b"hello", (tmp_path / "other.db").read_bytes()):
        with pytest.raises(BackupError, match="isn't a SplitLens Backup"):
            restore_backup(live, data, tmp_path / "safety")
    assert names(live) == ["Kept"]


def test_backup_from_a_newer_version_is_refused(live, tmp_path):
    newer = connect(tmp_path / "newer.db")
    init_db(newer)
    newer.execute("PRAGMA user_version = 99")
    newer.commit()
    newer.close()
    with pytest.raises(BackupError, match="newer version"):
        restore_backup(live, (tmp_path / "newer.db").read_bytes(), tmp_path / "safety")


def test_backups_in_the_same_second_keep_both(live, tmp_path):
    first, second = save_backup(live, tmp_path), save_backup(live, tmp_path)
    assert first.path != second.path and first.path.exists() and second.path.exists()
