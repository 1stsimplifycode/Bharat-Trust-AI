"""
Vercel serverless entrypoint.
"""
import os
import shutil
import sys
from pathlib import Path

# /var/task is the project root; backend/app is the Python package
_ROOT = Path(__file__).resolve().parent.parent  # /var/task
_BACKEND = _ROOT / "backend"

# Add backend/ to sys.path so `import app` finds backend/app/
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Seed DB
_TMP_DB = "/tmp/bharattrust.db"
for _seed_candidate in [
    _ROOT / "data" / "bharattrust.seed.db",
    _BACKEND / "bharattrust.db",
]:
    if not os.path.exists(_TMP_DB) and _seed_candidate.exists():
        shutil.copy(str(_seed_candidate), _TMP_DB)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TMP_DB}")

from app.main import app  # noqa: E402,F401
