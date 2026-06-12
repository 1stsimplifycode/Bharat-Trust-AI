"""
Vercel serverless entrypoint.

The `app` package lives at the project root (top-level /app/) and is bundled
via includeFiles in vercel.json. api/ contains ONLY this file so Vercel does
not mistake the package modules for separate serverless functions.
"""
import os
import shutil
import sys
from pathlib import Path

# /var/task is the Vercel project root; app/ is bundled there via includeFiles
_ROOT = Path(__file__).resolve().parent.parent  # go up from api/ to project root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Seed DB
_TMP_DB = "/tmp/bharattrust.db"
_SEED = _ROOT / "data" / "bharattrust.seed.db"
if not os.path.exists(_TMP_DB) and _SEED.exists():
    shutil.copy(str(_SEED), _TMP_DB)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB}")

from app.main import app  # noqa: E402,F401
