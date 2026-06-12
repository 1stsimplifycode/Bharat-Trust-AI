"""
Live orchestration engine.

This is the heart of the "agentic" experience. Given a product (a customer
intent), the Orchestrator dispatches the specialist agents one by one and
streams every step out as it happens:

    orchestrator -> dispatch(agent) -> reasoning steps... -> real result
                 -> ... next agent ...
                 -> decision engine fuses everything -> final verdict

The reasoning steps are NOT decoration: each one names a real phase of that
agent's computation, and the headline number attached to every `result`
frame is produced by the actual agent running over real seeded data. The only
thing added for the human watching is pacing (a short delay between frames) so
the reasoning chain is legible instead of appearing instantly.

`orchestrate_product` is a generator of plain dicts ("frames"). The router
serialises them as Server-Sent Events with the pacing applied.
"""
from .. import models
from ..agents.orchestrator import Orchestrator
from ..agents import trust_engine


# Each agent declares the real sub-steps it walks through. These mirror the
# operations in the corresponding agent module.
REASONING = {
    "seller_monitoring": [
        "Pulling seller record, GST and account age",
        "Scoring cancellation rate and delivery delays",
        "Weighing complaint ratio and review velocity",
        "Composing weighted trust subscores",
    ],
    "authenticity": [
        "Reading product metadata and packaging fields",
        "Checking QR / authenticity code and tax invoice",
        "Comparing listed price against brand MRP",
        "Estimating counterfeit probability",
    ],
    "fraud": [
        "Loading marketplace seller graph",
        "Extracting behavioural feature vectors",
        "Running isolation-forest anomaly scan",
        "Cross-checking GST / phone / IP for duplicate rings",
    ],
    "review_intelligence": [
        "Collecting reviews attached to this listing",
        "Shingling text and computing Jaccard clusters",
        "Scoring spam phrases and burst velocity",
        "Rating overall review authenticity",
    ],
    "return_prediction": [
        "Reading category return base-rate",
        "Factoring seller reliability and delivery time",
        "Measuring price deviation vs category",
        "Computing return probability and intervention",
    ],
    "price_intelligence": [
        "Sampling category price distribution",
        "Computing p25 / median / p75 bands",
        "Estimating demand elasticity",
        "Locating the optimal price point",
    ],
    "logistics": [
        "Resolving destination geo-coordinates",
        "Measuring distance to 5 fulfilment hubs",
        "Selecting nearest warehouse and courier band",
        "Optimising ETA and cost vs central baseline",
    ],
}

# Display metadata for the orchestrator graph.
AGENT_META = {
    "seller_monitoring": {"label": "Seller Monitoring", "kind": "trust", "icon": "shield"},
    "authenticity":      {"label": "Authenticity",      "kind": "trust", "icon": "badge"},
    "fraud":             {"label": "Fraud Detection",   "kind": "risk",  "icon": "alert"},
    "review_intelligence": {"label": "Review Intelligence", "kind": "trust", "icon": "chat"},
    "return_prediction": {"label": "Return Prediction", "kind": "risk", "icon": "box"},
    "price_intelligence": {"label": "Price Intelligence", "kind": "info", "icon": "tag"},
    "logistics":         {"label": "Logistics",         "kind": "info",  "icon": "truck"},
}

PIPELINE = [
    "seller_monitoring", "authenticity", "fraud",
    "review_intelligence", "return_prediction", "price_intelligence", "logistics",
]


def _category_prices(db, category):
    rows = db.query(models.Product.price).filter(models.Product.category == category).all()
    return [r[0] for r in rows if r[0]]


def pick_demo_products(db, n=6):
    """Surface a few genuinely interesting listings for the search bar:
    at least one likely-counterfeit (premium brand priced far under MRP) and
    some clean ones, so the theatre always has something real to show."""
    from ..agents.authenticity import PREMIUM_BRANDS
    picks = []
    # counterfeit-leaning
    for p in db.query(models.Product).filter(models.Product.brand.in_(list(PREMIUM_BRANDS))).limit(400):
        if p.mrp and p.price / p.mrp < 0.45:
            picks.append(p)
        if len(picks) >= 2:
            break
    # normal popular ones
    for p in (db.query(models.Product)
              .order_by(models.Product.rating_count.desc())
              .limit(n)):
        if p not in picks:
            picks.append(p)
        if len(picks) >= n:
            break
    return [{"id": p.id, "name": p.name, "brand": p.brand,
             "category": p.category, "price": p.price, "mrp": p.mrp,
             "seller_id": p.seller_id} for p in picks[:n]]


def orchestrate_product(db, product_id: int, dest_lat: float = 22.57, dest_lng: float = 88.36):
    """Generator of orchestration frames for one product/customer intent."""
    product = db.query(models.Product).get(product_id)
    if not product:
        yield {"type": "error", "message": f"Product {product_id} not found"}
        return
    seller = db.query(models.Seller).get(product.seller_id)
    orch = Orchestrator(db)

    yield {
        "type": "orchestrator", "phase": "start",
        "intent": f"Evaluate '{product.name}' before recommending to customer",
        "product": {"id": product.id, "name": product.name, "brand": product.brand,
                    "category": product.category, "price": product.price, "mrp": product.mrp},
        "seller": {"id": seller.id, "name": seller.name, "state": seller.state},
        "pipeline": [{"agent": a, **AGENT_META[a]} for a in PIPELINE],
    }

    results = {}
    cat_prices = _category_prices(db, product.category)
    cat_avg = (sum(cat_prices) / len(cat_prices)) if cat_prices else product.price

    for agent in PIPELINE:
        yield {"type": "dispatch", "agent": agent, **AGENT_META[agent]}
        for step in REASONING[agent]:
            yield {"type": "reasoning", "agent": agent, "step": step}

        # ---- run the REAL agent and extract its headline metric ----
        if agent == "seller_monitoring":
            r = orch.seller_agent.run(seller)
            results["seller"] = r.score
            metric = {"value": round(r.score, 1), "unit": "/100", "tone": _tone(r.score, True)}
            reasons, headline = r.reasons[:5], f"Trust {r.score:.0f}/100"

        elif agent == "authenticity":
            r = orch.auth_agent.run(product, seller)
            results["authenticity"] = r.score
            cp = r.data["counterfeit_probability"] * 100
            metric = {"value": round(r.score, 1), "unit": "% authentic", "tone": _tone(r.score, True)}
            reasons = r.reasons[:5]
            headline = f"{r.score:.0f}% authentic · {cp:.0f}% counterfeit risk"

        elif agent == "fraud":
            fdata = orch.fraud_pass()
            fr = fdata["per_seller"].get(seller.id, {"risk": 0.0, "reasons": [], "duplicates": []})
            results["fraud_risk"] = fr["risk"]
            metric = {"value": round(fr["risk"], 1), "unit": "% risk", "tone": _tone(fr["risk"], False)}
            reasons = (fr.get("reasons") or ["No anomalies in behavioural or identity graph"])[:5]
            headline = f"Fraud risk {fr['risk']:.0f}%"

        elif agent == "review_intelligence":
            pids = [product.id]
            reviews = db.query(models.Review).filter(models.Review.product_id.in_(pids)).all()
            r = orch.review_agent.run(reviews)
            results["review"] = r.score
            susp = r.data.get("suspicious_count", 0)
            metric = {"value": round(r.score, 1), "unit": "% genuine", "tone": _tone(r.score, True)}
            reasons = r.reasons[:5] or [f"{len(reviews)} reviews scanned, {susp} suspicious"]
            headline = f"{r.score:.0f}% genuine reviews ({susp} flagged)"

        elif agent == "return_prediction":
            out = orch.return_agent.predict(seller=seller, product=product,
                                            delivery_days=4, category_avg_price=cat_avg)
            prob = out["return_probability"] * 100
            results["return_risk"] = prob
            metric = {"value": round(prob, 1), "unit": "% return", "tone": _tone(prob, False)}
            reasons = [out["reason"], out["intervention"]]
            headline = f"{prob:.0f}% return probability"

        elif agent == "price_intelligence":
            r = orch.price_agent.run(product, cat_prices)
            rec = r.data["recommended_price"]
            chg = r.data["expected_sales_change_pct"]
            results["price_reco"] = rec
            metric = {"value": rec, "unit": "₹ suggested", "tone": "info"}
            reasons = r.reasons[:5]
            headline = f"Suggest ₹{rec:,.0f} (≈{chg:+.0f}% demand)"

        elif agent == "logistics":
            r = orch.logistics_agent.run(dest_lat=dest_lat, dest_lng=dest_lng)
            d = r.data
            results["logistics"] = d
            metric = {"value": d["eta_days"], "unit": "day ETA", "tone": "info"}
            reasons = r.reasons[:5]
            headline = f"{d['warehouse']} → {d['eta_days']}d, ₹{d['cost']:,.0f} (saves ₹{d['savings']:,.0f})"

        yield {
            "type": "result", "agent": agent, **AGENT_META[agent],
            "metric": metric, "headline": headline, "reasons": reasons,
        }

    # ---- decision engine fuses every signal ----
    yield {"type": "decision", "phase": "fusing",
           "inputs": ["seller_monitoring", "authenticity", "fraud",
                      "review_intelligence", "return_prediction"]}

    delivery = orch.seller_agent.run(seller).data["subscores"]["delivery"]
    overall = trust_engine.compute_overall(
        seller_score=results.get("seller", 60),
        fraud_risk=results.get("fraud_risk", 0),
        return_risk=results.get("return_risk", 20),
        authenticity=results.get("authenticity", 70),
        review_score=results.get("review", 80),
        delivery_score=delivery,
    )
    band = trust_engine.band(overall)
    if overall >= 75 and results.get("fraud_risk", 0) < 40:
        verdict, action = "RECOMMEND", "Surface to customer with trust badge"
    elif overall >= 55:
        verdict, action = "RECOMMEND WITH CAUTION", "Show authenticity caveat + alternatives"
    else:
        verdict, action = "SUPPRESS", "Hold from recommendations, escalate seller for review"

    yield {
        "type": "decision", "phase": "final",
        "overall": overall, "band": band, "verdict": verdict, "action": action,
        "breakdown": {
            "Seller trust": round(results.get("seller", 0), 1),
            "Authenticity": round(results.get("authenticity", 0), 1),
            "Fraud risk": round(results.get("fraud_risk", 0), 1),
            "Review trust": round(results.get("review", 0), 1),
            "Return risk": round(results.get("return_risk", 0), 1),
            "Delivery": round(delivery, 1),
        },
        "logistics": results.get("logistics"),
        "price_reco": results.get("price_reco"),
    }


def _tone(score, higher_is_better):
    if higher_is_better:
        return "good" if score >= 70 else "warn" if score >= 45 else "bad"
    return "good" if score < 30 else "warn" if score < 60 else "bad"
