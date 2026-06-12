<div align="center">

# 🛡️ BharatTrust AI

**Agentic AI Marketplace Intelligence Platform for Bharat**

Seven specialist agents, a live orchestrator you can *watch* think, and an
explainable Decision Engine — over 500 sellers, 3,000 listings, 5,000 reviews
of realistic marketplace data with planted fraud rings the agents genuinely catch.

![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE%20streaming-009688?logo=fastapi&logoColor=white)
![Frontend](https://img.shields.io/badge/frontend-zero%20JS%20deps-A78BFA)
![License](https://img.shields.io/badge/license-MIT-34D399)
![CI](https://img.shields.io/badge/tests-6%20passing-34D399)

<img src="docs/screenshots/orchestrator.png" width="85%" alt="Orchestrator theatre — agents dispatched live, reasoning streamed, decision fused" />

</div>

---

## Why this isn't a dashboard

The UI doesn't poll a finished answer — it subscribes to a **Server-Sent Events
stream** and watches the Orchestrator dispatch each agent, narrate its real
computation phases, return its computed score, and hand everything to the
Decision Engine for a fused, explainable verdict:

```
customer intent ──► Orchestrator ══ SSE ══► browser
                        │                   (graph lights up, console types,
                        ▼                    agent cards fill in live)
   Seller Monitoring → Authenticity → Fraud → Review Intelligence
        → Return Prediction → Price Intelligence → Logistics
                        │
                        ▼
        Decision Engine → RECOMMEND / RECOMMEND WITH CAUTION / SUPPRESS
                          + six-signal breakdown of WHY
```

A second stream (`/api/events/stream`) powers the **Admin ops room**: fraud
rings, counterfeit listings and return-risk interventions surface as the
agents flag them, plotting onto a live risk map of India.

| Admin ops room | Seller studio |
|---|---|
| <img src="docs/screenshots/admin-ops.png" width="100%"/> | <img src="docs/screenshots/seller-studio.png" width="100%"/> |

## The agents (all real computation, zero mocks)

| Agent | Technique | Output |
|---|---|---|
| 🚨 Fraud Detection | Isolation Forest **+** GST/phone/IP identity graph (pure-Python robust z-score fallback when compiled DLLs are unavailable) | risk 0–100 + evidence |
| 🛡️ Seller Monitoring | weighted behavioural scoring (cancellations, delays, complaints, volatility) | trust 0–100 + reasons |
| 🏷️ Authenticity | metadata + price-vs-MRP coherence for premium brands (OCR hook ready) | % authentic + counterfeit prob |
| 💬 Review Intelligence | Jaccard shingle near-duplicate clustering + spam heuristics | % genuine + flagged reviews |
| 📦 Return Prediction | interpretable logistic model over category/seller/price features | probability + intervention |
| 💸 Price Intelligence | category quantiles (p25/median/p75) + elasticity | recommended price |
| 🚚 Logistics | haversine routing across a 5-hub network vs central baseline | warehouse, ETA, ₹ savings |
| 🗣️ Support | intent routing + DB-backed actions in 11 Indian languages | grounded replies |
| ⚖️ Trust Engine | weighted fusion of six signals | overall score + band |

**The proof it's real:** the seed plants a 3-seller ring sharing one phone
number and IP, plus premium-brand listings at 26–33% of MRP. The agents are
never told who's bad — they *find* them (ring flagged at 84–96 risk via the
identity graph; counterfeits at 44% authenticity via price coherence). The CI
suite asserts exactly this on every push, on both the full-ML and
pure-Python backends.

## Quick start (local — zero external setup)

**Windows:** double-click `setup.bat`, then `run.bat` → opens `http://localhost:8000`

**macOS / Linux:**
```bash
./setup.sh && ./run.sh        # dashboard at http://localhost:8000, API docs at /docs
```

**Manual:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python -m app.seed            # 500 sellers / 3,000 products / planted anomalies
uvicorn app.main:app --port 8000
```

Demo flow that lands hardest: click the **Adidas pick with the red dot**
(planted counterfeit) and watch the Authenticity agent catch it live, then
open **Admin Ops** to see the fraud ring surface in the event stream.

## Deploy

### Vercel (one click)

```bash
npm i -g vercel && vercel        # from the repo root — that's it
```

or import the GitHub repo at [vercel.com/new](https://vercel.com/new) — no
configuration needed. The repo is Vercel-native:

- `public/` → static frontend, served from the edge
- `api/index.py` → the FastAPI app as a serverless function (`vercel.json`
  rewrites `/api/*`, `/docs`, `/health` to it)
- `data/bharattrust.seed.db` → pre-seeded snapshot copied to `/tmp` on cold
  start (serverless filesystems are read-only)
- root `requirements.txt` is deliberately slim — no scikit-learn/scipy — so
  the bundle stays small; the fraud agent auto-degrades to its pure-Python
  backend with identical interfaces (CI tests this exact path)

> **Streaming note:** SSE pacing is guaranteed on local/Render/Railway runs.
> Some Vercel plans buffer Python responses; if so, frames arrive together at
> stream end and the UI still renders everything — just less theatrically.
> For judged demos, run locally or on Render.

### Render / Railway (long-lived server, guaranteed SSE)

`render.yaml` blueprint and `backend/Procfile` are included:

```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Supabase / Postgres

Set one env var — the schema creates itself on startup:

```
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres
```

## Key API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/orchestrate/picks` | interesting listings (incl. planted counterfeits) |
| GET | `/api/orchestrate/stream?product_id=` | **SSE** — live agent-by-agent evaluation |
| GET | `/api/events/stream` | **SSE** — live marketplace ops feed |
| GET | `/api/analytics/overview` | KPIs + marketplace health |
| GET | `/api/fraud/scan?min_risk=50` | fraud scan with evidence |
| GET | `/api/sellers/{id}/trust` | full orchestrated trust evaluation |
| POST | `/api/returns/predict` | pre-shipment return probability |
| POST | `/api/price/recommend` | optimal price recommendation |
| POST | `/api/logistics/optimize` | warehouse + route + savings |
| POST | `/api/support/ask` | multilingual support agent |

Interactive docs at `/docs`.

## Repository layout

```
├── api/index.py            Vercel serverless entrypoint
├── backend/
│   ├── app/
│   │   ├── agents/         the nine agents + trust engine + orchestrator
│   │   ├── orchestration/  SSE frame generators (live.py, events.py)
│   │   ├── routers/        REST (api.py) + streaming (stream.py)
│   │   ├── models.py · seed.py · main.py · database.py
│   └── requirements.txt    full stack (Isolation Forest) for local/Render
├── public/index.html       the entire frontend — zero JS dependencies
├── data/bharattrust.seed.db   pre-seeded snapshot for serverless deploys
├── tests/test_smoke.py     proves planted anomalies are genuinely caught
├── .github/workflows/ci.yml   two jobs: full-ML and pure-Python paths
├── vercel.json · render.yaml · setup/run scripts
```

## Honesty of scope

Every score is computed at request time from the database — but these are
**algorithmic agents** (statistics, one ML model, graph analysis, heuristics),
not LLM agents. The console's reasoning lines are honest narrations of each
agent's real computation phases, paced for legibility; no language model
"thinks" in the loop. That mirrors how production marketplace-integrity
systems actually work. Documented hooks for the natural next milestones:
Mistral-generated decision rationales, OCR-backed packaging verification
(`ocr_text` param wired), real translation services, production auth.

## Troubleshooting

**Windows: `DLL load failed … An Application Control policy has blocked this file`** —
Smart App Control blocks scipy's unsigned DLLs. Handled automatically: the
fraud agent detects the blocked import and switches to its pure-Python
backend (same interface, same planted-ring detection). No need to touch
Windows security.

**`ERR_CONNECTION_REFUSED`** — the server didn't start; scroll the `run.bat`
console up for the actual Python error.

## License

MIT — see [LICENSE](LICENSE).
