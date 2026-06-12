"""
Vercel serverless entrypoint.

Vercel functions get a read-only filesystem except /tmp, so on cold start we
copy the bundled pre-seeded SQLite snapshot into /tmp and point DATABASE_URL
at it BEFORE importing the app. Writes go to /tmp and last for the life of
the instance, which is fine for a demo.

The `app` package lives in api/app/ (co-located so Vercel auto-bundles it).
Heavy compiled deps (scikit-learn/scipy) are absent from the root
requirements.txt — the Fraud Detection agent auto-degrades to its pure-Python
robust z-score backend, keeping the serverless bundle small.
"""
import os
import shutil
import sys
from pathlib import Path

# api/ is at /var/task/api/ on Vercel; add it to sys.path so `app` is importable
_API_DIR = Path(__file__).resolve().parent
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

# Seed DB: copy from api/data/ to /tmp on cold start
_TMP_DB = "/tmp/bharattrust.db"
_SEED = _API_DIR / "data" / "bharattrust.seed.db"

if not os.path.exists(_TMP_DB) and _SEED.exists():
    shutil.copy(str(_SEED), _TMP_DB)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB}")

from app.main import app  # noqa: E402,F401  (Vercel picks up `app` as ASGI)
