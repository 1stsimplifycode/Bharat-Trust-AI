"""
Smoke tests — prove the platform genuinely computes, not mocks.

Run from repo root:  pytest tests -q
(CI seeds backend/bharattrust.db first via `python -m app.seed`.)
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "backend"))
# The default sqlite URL is CWD-relative; pin it to the seeded file so the
# suite passes from the repo root (local and CI alike).
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_ROOT / 'backend' / 'bharattrust.db'}")

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_overview_kpis_computed():
    d = client.get("/api/analytics/overview").json()
    assert d["sellers"] == 500
    assert d["products"] == 3000
    assert 0 < d["marketplace_health"] <= 100


def test_fraud_agent_catches_planted_ring():
    """The seed plants a 3-seller shared phone+IP ring. The agent must find
    it through its own identity-graph logic — nothing is hardcoded."""
    d = client.get("/api/fraud/scan").json()
    assert d["flagged_count"] >= 3
    top = d["sellers"][0]
    assert top["risk"] >= 70
    evidence = " ".join(top.get("reasons", []))
    assert "Shared" in evidence  # identity-graph evidence present


def test_trust_evaluation_is_explainable():
    d = client.get("/api/sellers/20/trust").json()
    assert 0 <= d["overall"] <= 100
    assert set(d["components"]) == {
        "seller", "fraud_risk", "return_risk", "authenticity", "review", "delivery"
    }
    assert d["reasons"], "every score must explain why"


def test_orchestrate_stream_emits_full_pipeline():
    pid = client.get("/api/orchestrate/picks").json()["picks"][0]["id"]
    counts = {}
    with client.stream("GET", f"/api/orchestrate/stream?product_id={pid}&pace=0") as r:
        assert r.status_code == 200
        assert "text/event-stream" in r.headers["content-type"]
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line.split("event: ")[1]
                counts[ev] = counts.get(ev, 0) + 1
    assert counts.get("dispatch") == 7, counts
    assert counts.get("result") == 7, counts
    assert counts.get("decision") == 2, counts
    assert counts.get("reasoning", 0) >= 20, counts


def test_support_agent_multilingual():
    r = client.post("/api/support/ask",
                    json={"message": "where is my order", "lang": "hi", "order_id": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["reply"]
    assert body["data"]["lang"] == "hi"
