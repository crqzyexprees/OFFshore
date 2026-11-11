"""Makes the app's `backend` package importable from these scripts, so training
uses the same feature encoding and vocabulary as the app."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
