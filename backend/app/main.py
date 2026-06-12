"""
BharatTrust AI — FastAPI entrypoint.

Self-sufficient across deploy targets:
- Local / Render / Railway: serves the dashboard from /public, SQLite next to
  the backend (or DATABASE_URL).
- Vercel serverless: detects the read-only filesystem (VERCEL env), copies the
  bundled pre-seeded snapshot (data/bharattrust.seed.db) to /tmp and points
  DATABASE_URL at it — regardless of which entry file the platform imported.
The frontend is located by probing every plausible bundle layout and the HTML
is cached in memory at startup, so static serving works even when the deploy
platform rearranges paths.
"""
import os
import shutil
import logging
from pathlib import Path

# ---------- Vercel / serverless bootstrap (MUST run before importing .database) ----------
def _bootstrap_serverless_db():
    if os.getenv("DATABASE_URL"):
        return  # explicitly configured (e.g. Supabase) — respect it
    if not (os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME")):
        return  # normal machine — default local SQLite is fine
    tmp_db = "/tmp/bharattrust.db"
    if not os.path.exists(tmp_db):
        here = Path(__file__).resolve()
        candidates = [
            *(p / "data" / "bharattrust.seed.db" for p in list(here.parents)[:5]),
            Path.cwd() / "data" / "bharattrust.seed.db",
            Path("/var/task/data/bharattrust.seed.db"),
        ]
        for c in candidates:
            try:
                if c.exists():
                    shutil.copy(str(c), tmp_db)
                    break
            except OSError:
                continue
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp_db}"


_bootstrap_serverless_db()

from fastapi import FastAPI                      # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles      # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from .database import Base, engine, SessionLocal  # noqa: E402
from .routers import api, stream                 # noqa: E402

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bharattrust")

app = FastAPI(
    title="BharatTrust AI",
    description="Agentic AI Marketplace Intelligence Platform for Bharat",
    version="1.1.0",
)

origins = os.getenv("FRONTEND_ORIGIN", "*").split(",")
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(api.router)
app.include_router(stream.router)


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)
    log.info("Tables ensured. API ready at /docs")


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "bharattrust-ai"}


# ---------- frontend: probe every plausible layout, cache the HTML ----------
def _find_frontend_dir():
    here = Path(__file__).resolve()
    candidates = [
        *(p / "public" for p in list(here.parents)[:5]),
        Path.cwd() / "public",
        Path("/var/task/public"),
    ]
    for c in candidates:
        try:
            if (c / "index.html").exists():
                return c
        except OSError:
            continue
    return None


FRONTEND_DIR = _find_frontend_dir()
_INDEX_HTML = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8") if FRONTEND_DIR else None

if FRONTEND_DIR:
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def index():
    if _INDEX_HTML:
        return HTMLResponse(_INDEX_HTML)
    return JSONResponse({
        "service": "bharattrust-ai",
        "note": "frontend bundle not found on this deployment — API is live",
        "try": ["/docs", "/health", "/api/analytics/overview"],
    })


@app.get("/api/system", tags=["system"])
def system_status():
    """One-look deployment diagnostic: which ML backend is active, whether the
    seeded DB and frontend were found, and where we're running."""
    from .agents.fraud_detection import ML_BACKEND
    from . import models
    db = SessionLocal()
    try:
        sellers = db.query(models.Seller).count()
        products = db.query(models.Product).count()
    finally:
        db.close()
    return {
        "service": "bharattrust-ai",
        "ml_backend": ML_BACKEND,
        "db": {"url_scheme": os.getenv("DATABASE_URL", "sqlite (local default)").split(":")[0],
               "sellers": sellers, "products": products},
        "frontend_found": FRONTEND_DIR is not None,
        "platform": "vercel" if os.getenv("VERCEL") else "server",
    }