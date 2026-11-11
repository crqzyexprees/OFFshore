import os
import shutil
from pathlib import Path

HOST = "127.0.0.1"
PORT = int(os.environ.get("SPLITLENS_API_PORT", "18765"))

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
MODEL_DIR = BACKEND_DIR / "models"

APP_DATA = Path.home() / ".local" / "share" / "splitlens"
DB_PATH = APP_DATA / "splitlens.db"

# Backups go where the user can find and copy them; the copy taken before each
# restore stays with the app's data.
BACKUP_DIR = Path(os.environ.get("SPLITLENS_BACKUP_DIR", Path.home() / "Documents" / "SplitLens Backups"))
SAFETY_DIR = APP_DATA / "before-restore"

# Before it was renamed SplitLens, the app was called Finance.
_FINANCE_DATA = Path.home() / ".local" / "share" / "finance-app"


def move_finance_data(old: Path = _FINANCE_DATA, new: Path = APP_DATA) -> None:
    """Moves a Finance database to SplitLens's place, once: only when SplitLens
    has none yet. The -wal/-shm files move with it, so nothing written is lost."""
    if new.exists() or not (old / "finance.db").exists():
        return
    shutil.move(old, new)
    for suffix in ("", "-wal", "-shm"):
        src = new / f"finance.db{suffix}"
        if src.exists():
            src.rename(new / f"splitlens.db{suffix}")
