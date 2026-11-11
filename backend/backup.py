"""Backups: the whole database copied to a file, and put back from one.

A Backup without a password is a plain SQLite file, readable by anyone who
can open it. With a password it is encrypted: the database is compressed and
sealed with AES-256-GCM under a key derived from the password with scrypt.
The password is never stored, so a forgotten one can't be recovered.

Encrypted file layout (the header is authenticated along with the data):
    MAGIC (16) | version (1) | log2 N, r, p (3) | salt (16) | nonce (12) | ciphertext

Restoring checks that the file is a SplitLens database this version can read,
saves a copy of the current database first, then replaces it.
"""

import hashlib
import os
import sqlite3
import tempfile
import zlib
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from backend.db import SCHEMA_VERSION, connect, init_db

MAGIC = b"SPLITLENS-BACKUP"
VERSION = 1
_SQLITE_MAGIC = b"SQLite format 3\x00"
_LOG2_N, _R, _P = 15, 8, 1  # scrypt: 32 MiB of memory per guess
_SALT, _NONCE = 16, 12
MIN_PASSWORD = 8
ENCRYPTED_SUFFIX = ".splitlens-backup"
PLAIN_SUFFIX = ".db"
_REQUIRED_TABLES = {"accounts", "statements", "transactions"}


class BackupError(Exception):
    """The backup or restore can't go ahead. Nothing was changed."""


@dataclass(frozen=True)
class Saved:
    path: Path
    encrypted: bool
    size: int


def save_backup(conn: sqlite3.Connection, directory: Path, password: str | None = None) -> Saved:
    if password is not None:
        _check_password(password)
    data = _snapshot(conn)
    encrypted = password is not None
    if encrypted:
        data = encrypt(data, password)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    suffix = ENCRYPTED_SUFFIX if encrypted else PLAIN_SUFFIX
    path = directory / f"splitlens-{stamp}{suffix}"
    n = 1
    while path.exists():  # two Backups in the same second
        n += 1
        path = directory / f"splitlens-{stamp}-{n}{suffix}"
    _write_private(path, data)
    return Saved(path, encrypted, len(data))


def restore_backup(
    conn: sqlite3.Connection, data: bytes, safety_dir: Path, password: str | None = None
) -> Path:
    """Replaces the database `conn` is open on with the Backup in `data`.
    Returns where the database as it was before is saved."""
    if data.startswith(MAGIC):
        if not password:
            raise BackupError("This Backup is encrypted. Enter its password.")
        data = decrypt(data, password)
    elif not data.startswith(_SQLITE_MAGIC):
        raise BackupError("This file isn't a SplitLens Backup.")

    with tempfile.TemporaryDirectory() as tmp:
        restored_path = Path(tmp) / "restored.db"
        restored_path.write_bytes(data)
        with closing(connect(restored_path)) as restored:
            _check_restorable(restored)
            safety = save_backup(conn, safety_dir)
            restored.backup(conn)
    init_db(conn)  # brings an older Backup up to the current schema
    return safety.path


# ── Encryption ──

def encrypt(data: bytes, password: str) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt, nonce = os.urandom(_SALT), os.urandom(_NONCE)
    header = MAGIC + bytes([VERSION, _LOG2_N, _R, _P]) + salt + nonce
    sealed = AESGCM(_key(password, salt, _LOG2_N, _R, _P)).encrypt(nonce, zlib.compress(data), header)
    return header + sealed


def decrypt(blob: bytes, password: str) -> bytes:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    fixed = len(MAGIC) + 4
    header_end = fixed + _SALT + _NONCE
    if len(blob) <= header_end:
        raise BackupError("This Backup is damaged.")
    version, log2_n, r, p = blob[len(MAGIC):fixed]
    if version != VERSION:
        raise BackupError("This Backup was made by a newer version of SplitLens.")
    if not (10 <= log2_n <= 20 and 1 <= r <= 16 and 1 <= p <= 4):
        raise BackupError("This Backup is damaged.")
    salt, nonce = blob[fixed:fixed + _SALT], blob[fixed + _SALT:header_end]
    try:
        sealed = AESGCM(_key(password, salt, log2_n, r, p)).decrypt(nonce, blob[header_end:], blob[:header_end])
    except InvalidTag:
        raise BackupError("Wrong password, or the Backup is damaged.") from None
    return zlib.decompress(sealed)


def _key(password: str, salt: bytes, log2_n: int, r: int, p: int) -> bytes:
    n = 1 << log2_n
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=256 * n * r, dklen=32)


def _check_password(password: str) -> None:
    if len(password) < MIN_PASSWORD:
        raise BackupError(f"Use a password of at least {MIN_PASSWORD} characters.")


# ── Files ──

def _snapshot(conn: sqlite3.Connection) -> bytes:
    """A consistent copy of the live database, WAL included."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "snapshot.db"
        with closing(sqlite3.connect(path)) as copy:
            conn.backup(copy)
        return path.read_bytes()


def _write_private(path: Path, data: bytes) -> None:
    """Only the owner can read it; a half-written file is never left behind."""
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        partial.replace(path)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _check_restorable(db: sqlite3.Connection) -> None:
    try:
        ok = db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        version = db.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.DatabaseError:
        ok, tables, version = False, set(), 0
    if not ok:
        raise BackupError("This Backup is damaged.")
    if version > SCHEMA_VERSION:
        raise BackupError("This Backup was made by a newer version of SplitLens. Update the app first.")
    if version < 2 or not _REQUIRED_TABLES <= tables:
        raise BackupError("This file isn't a SplitLens Backup.")
