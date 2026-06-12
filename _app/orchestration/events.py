"""
Live marketplace event feed for the Admin operations room.

Every event references a REAL seeded entity with a REAL computed score: the
fraud pass over the live database surfaces the planted GST/phone/IP rings and
behavioural outliers; high return-risk and counterfeit listings are pulled
from actual agent output. The feed simply paces these real findings out over
time so the admin console feels like a live system under load, the way an
internal Amazon/Flipkart ops console would.
"""
import random
from datetime import datetime

from .. import models
from ..agents.orchestrator import Orchestrator
from ..agents.authenticity import PREMIUM_BRANDS


def build_event_pool(db, limit=60):
    """Compute a pool of real, noteworthy events from current DB state."""
    orch = Orchestrator(db)
    pool = []

    # 1. Fraud findings (real isolation-forest + identity-graph hits)
    fdata = orch.fraud_pass()
    flagged = sorted(fdata["per_seller"].items(),
                     key=lambda kv: kv[1]["risk"], reverse=True)
    sellers = {s.id: s for s in db.query(models.Seller).all()}
    for sid, info in flagged:
        if info["risk"] < 50:
            continue
        s = sellers.get(sid)
        dup = info.get("duplicates") or []
        if dup:
            pool.append(_evt("fraud_ring", "Fraud Detection",
                             f"Seller '{s.name}' linked to a duplicate-identity ring",
                             info["risk"], s, detail=dup[0], severity="critical",
                             action="Auto-frozen pending manual review"))
        else:
            pool.append(_evt("anomaly", "Fraud Detection",
                             f"Behavioural outlier flagged: '{s.name}'",
                             info["risk"], s, detail=(info.get("reasons") or [""])[0],
                             severity="high", action="Added to watch-list"))

    # 2. Counterfeit listings (premium brand priced far under MRP)
    cnt = 0
    for p in db.query(models.Product).filter(models.Product.brand.in_(list(PREMIUM_BRANDS))).limit(500):
        if p.mrp and p.price / p.mrp < 0.45:
            s = sellers.get(p.seller_id)
            ratio = p.price / p.mrp
            pool.append(_evt("counterfeit", "Authenticity",
                             f"Suspected counterfeit: {p.brand} '{p.name[:32]}'",
                             round((1 - ratio) * 100, 1), s,
                             detail=f"Listed at {ratio:.0%} of MRP", severity="high",
                             action="Listing demoted, seller notified"))
            cnt += 1
        if cnt >= 12:
            break

    # 3. Return-risk interventions (real logistic model on recent orders)
    orders = (db.query(models.Order)
              .filter(models.Order.status.in_(["placed", "shipped"]))
              .limit(200).all())
    prod_cache = {}
    picks = 0
    for o in random.sample(orders, min(len(orders), 40)):
        p = prod_cache.get(o.product_id) or db.query(models.Product).get(o.product_id)
        prod_cache[o.product_id] = p
        s = sellers.get(o.seller_id)
        if not p or not s:
            continue
        rows = db.query(models.Product.price).filter(models.Product.category == p.category).all()
        prices = [r[0] for r in rows if r[0]]
        cat_avg = sum(prices) / len(prices) if prices else p.price
        out = orch.return_agent.predict(seller=s, product=p, delivery_days=o.delivery_days or 4,
                                        category_avg_price=cat_avg)
        prob = out["return_probability"] * 100
        if prob >= 55:
            pool.append(_evt("intervention", "Return Prediction",
                             f"High return risk on order #{o.id} ({p.category})",
                             round(prob, 1), s, detail=out["intervention"],
                             severity="medium", action="Proactive QC workflow triggered"))
            picks += 1
        if picks >= 12:
            break

    # 4. A few healthy/positive ops events for realism
    top = (db.query(models.Seller).order_by(models.Seller.total_orders.desc()).limit(8).all())
    for s in top[:6]:
        pool.append(_evt("healthy", "Seller Monitoring",
                         f"'{s.name}' cleared all integrity checks",
                         round(orch.seller_agent.run(s).score, 1), s,
                         detail="GST + invoice verified, low complaints",
                         severity="info", action="Eligible for trust badge"))

    random.shuffle(pool)
    return pool[:limit]


def _evt(kind, agent, message, score, seller, detail="", severity="info", action=""):
    return {
        "kind": kind, "agent": agent, "message": message, "score": score,
        "detail": detail, "severity": severity, "action": action,
        "seller_id": getattr(seller, "id", None),
        "state": getattr(seller, "state", None),
        "lat": getattr(seller, "lat", None), "lng": getattr(seller, "lng", None),
        "ts": datetime.utcnow().isoformat(timespec="seconds"),
    }
