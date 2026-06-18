from pathlib import Path

HOST = "127.0.0.1"
PORT = int(__import__("os").environ.get("FINANCE_API_PORT", "18765"))

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
MODEL_DIR = BACKEND_DIR / "models"

APP_DATA = Path.home() / ".local" / "share" / "finance-app"
DB_PATH = APP_DATA / "finance.db"
