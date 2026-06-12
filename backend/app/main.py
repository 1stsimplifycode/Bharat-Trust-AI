"""
BharatTrust AI — FastAPI entrypoint.

Mounts the API routers, serves the static frontend dashboard, enables CORS for
the Vercel frontend, and exposes auto docs at /docs. Creates tables on startup
(seed separately with `python -m app.seed`).
"""
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .database import Base, engine
from .routers import api, stream

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("bharattrust")

app = FastAPI(
    title="BharatTrust AI",
    description="Agentic AI Marketplace Intelligence Platform for Bharat",
    version="1.0.0",
)

# CORS — allow the deployed frontend (set FRONTEND_ORIGIN on Railway/Render)
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


# ---- serve the static frontend (single-page dashboard) ----
# Lives in /public so Vercel serves it as static assets on serverless deploys,
# while local / Render / Railway runs serve it straight from FastAPI.
FRONTEND_DIR = Path(__file__).resolve().parents[2] / "public"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(str(FRONTEND_DIR / "index.html"))
