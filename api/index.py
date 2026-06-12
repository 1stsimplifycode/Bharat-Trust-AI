"""
Vercel serverless entrypoint.

Vercel functions get a read-only filesystem except /tmp, so on cold start we
copy the bundled pre-seeded SQLite snapshot (data/bharattrust.seed.db — the
same data run.bat seeds locally, planted fraud rings included) into /tmp and
point DATABASE_URL at it BEFORE importing the app. Writes (trust-score
persistence, review mutations) go to /tmp and last for the life of the
instance, which is exactly right for a demo.

Heavy compiled deps (scikit-learn/scipy) are intentionally absent from the
root requirements.txt that Vercel installs — the Fraud Detection agent
auto-degrades to its pure-Python robust z-score backend, keeping the
serverless bundle small and cold starts fast. Local runs via run.bat still
use backend/requirements.txt and get the full Isolation Forest.
"""
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

_TMP_DB = "/tmp/bharattrust.db"
_SEED = ROOT / "data" / "bharattrust.seed.db"

if not os.path.exists(_TMP_DB) and _SEED.exists():
    shutil.copy(str(_SEED), _TMP_DB)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB}")

from app.main import app  # noqa: E402,F401  (Vercel picks up `app` as ASGI)
