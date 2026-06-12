"""
Streaming (Server-Sent Events) router.

These endpoints turn the agent pipeline into something you can WATCH:
  GET /api/orchestrate/picks          -> interesting listings to evaluate
  GET /api/orchestrate/stream         -> live agent-by-agent evaluation (SSE)
  GET /api/events/stream              -> live marketplace ops feed (SSE)

SSE is used (not websockets) so it works over plain HTTP with zero client
libraries: the browser's native EventSource consumes it directly.
"""
import asyncio
import json

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ..database import SessionLocal
from ..orchestration.live import orchestrate_product, pick_demo_products
from ..orchestration.events import build_event_pool

router = APIRouter()


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/api/orchestrate/picks", tags=["orchestrate"])
def orchestrate_picks():
    db = SessionLocal()
    try:
        return {"picks": pick_demo_products(db, n=6)}
    finally:
        db.close()


@router.get("/api/orchestrate/stream", tags=["orchestrate"])
async def orchestrate_stream(
    product_id: int = Query(...),
    dest_lat: float = 22.57,
    dest_lng: float = 88.36,
    pace: float = 0.5,
):
    """Stream the orchestrator dispatching every agent for one listing.

    `pace` is the per-frame delay in seconds (purely for legibility — the
    computation itself is synchronous and real). Reasoning steps tick faster
    than results so the chain reads naturally.
    """
    async def gen():
        db = SessionLocal()
        try:
            for frame in orchestrate_product(db, product_id, dest_lat, dest_lng):
                yield _sse(frame["type"], frame)
                t = frame.get("type")
                if t == "reasoning":
                    await asyncio.sleep(pace * 0.45)
                elif t == "result":
                    await asyncio.sleep(pace * 1.3)
                elif t in ("dispatch", "decision"):
                    await asyncio.sleep(pace * 0.8)
                else:
                    await asyncio.sleep(pace)
            yield _sse("done", {"ok": True})
        finally:
            db.close()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@router.get("/api/events/stream", tags=["events"])
async def events_stream(interval: float = 1.4):
    """Live marketplace ops feed. Computes a pool of real findings, then paces
    them out; when the pool is exhausted it recomputes, so the feed never dies.
    """
    async def gen():
        db = SessionLocal()
        try:
            while True:
                pool = build_event_pool(db, limit=60)
                if not pool:
                    await asyncio.sleep(interval)
                    continue
                for evt in pool:
                    yield _sse("event", evt)
                    await asyncio.sleep(interval)
        finally:
            db.close()

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})
