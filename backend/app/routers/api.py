"""
All REST routers.

Endpoints are real: they query the seeded DB and run the live agents.
Grouped with tags so they render cleanly in the auto Swagger docs at /docs.
"""
import json
from collections import Counter
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas
from ..agents.orchestrator import Orchestrator
from ..agents.price_intelligence import PriceIntelligenceAgent
from ..agents.return_prediction import ReturnPredictionAgent
from ..agents.logistics import LogisticsOptimizationAgent
from ..agents.support import CustomerSupportAgent

router = APIRouter()


# ----------------------- SELLERS -----------------------
@router.get("/api/sellers", tags=["sellers"])
def list_sellers(db: Session = Depends(get_db),
                 limit: int = Query(50, le=500), offset: int = 0,
                 sort: str = "id"):
    q = db.query(models.Seller)
    rows = q.offset(offset).limit(limit).all()
    return [{
        "id": s.id, "name": s.name, "state": s.state, "city": s.city,
        "total_orders": s.total_orders, "cancellation_rate": s.cancellation_rate,
        "avg_delivery_delay_days": s.avg_delivery_delay_days,
        "complaint_count": s.complaint_count, "verified_invoices": s.verified_invoices,
    } for s in rows]


@router.get("/api/sellers/{seller_id}", tags=["sellers"])
def get_seller(seller_id: int, db: Session = Depends(get_db)):
    s = db.query(models.Seller).get(seller_id)
    if not s:
        raise HTTPException(404, "Seller not found")
    products = [{"id": p.id, "name": p.name, "price": p.price,
                 "avg_rating": p.avg_rating} for p in s.products[:20]]
    return {"id": s.id, "name": s.name, "gst_number": s.gst_number,
            "phone": s.phone, "ip_address": s.ip_address, "state": s.state,
            "city": s.city, "verified_invoices": s.verified_invoices,
            "total_orders": s.total_orders,
            "cancellation_rate": s.cancellation_rate,
            "avg_delivery_delay_days": s.avg_delivery_delay_days,
            "complaint_count": s.complaint_count,
            "price_volatility": s.price_volatility,
            "review_velocity": s.review_velocity,
            "product_count": len(s.products), "products": products}


@router.get("/api/sellers/{seller_id}/trust", tags=["trust"])
def seller_trust(seller_id: int, db: Session = Depends(get_db)):
    """Run the full orchestrated evaluation for one seller (live)."""
    orch = Orchestrator(db)
    result = orch.evaluate_seller(seller_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    result["activity"] = orch.activity_log()
    return result


# ----------------------- PRODUCTS -----------------------
@router.get("/api/products", tags=["products"])
def list_products(db: Session = Depends(get_db),
                  q: str | None = None, category: str | None = None,
                  limit: int = Query(40, le=200), offset: int = 0):
    query = db.query(models.Product)
    if q:
        query = query.filter(models.Product.name.ilike(f"%{q}%"))
    if category:
        query = query.filter(models.Product.category == category)
    rows = query.offset(offset).limit(limit).all()
    return [{"id": p.id, "name": p.name, "brand": p.brand, "category": p.category,
             "price": p.price, "mrp": p.mrp, "avg_rating": p.avg_rating,
             "rating_count": p.rating_count, "seller_id": p.seller_id,
             "has_qr": p.has_qr, "image_url": p.image_url} for p in rows]


@router.get("/api/products/{product_id}/authenticity", tags=["trust"])
def product_authenticity(product_id: int, db: Session = Depends(get_db)):
    from ..agents.authenticity import ProductAuthenticityAgent
    p = db.query(models.Product).get(product_id)
    if not p:
        raise HTTPException(404, "Product not found")
    seller = db.query(models.Seller).get(p.seller_id)
    res = ProductAuthenticityAgent().run(p, seller)
    return res.dict()


@router.get("/api/products/{product_id}/reviews", tags=["reviews"])
def product_reviews(product_id: int, db: Session = Depends(get_db)):
    from ..agents.review_intelligence import ReviewIntelligenceAgent
    reviews = db.query(models.Review).filter(
        models.Review.product_id == product_id).all()
    res = ReviewIntelligenceAgent().run(reviews)
    db.commit()
    return {"summary": res.dict(),
            "reviews": [{"id": r.id, "rating": r.rating, "text": r.text,
                         "authenticity_score": r.authenticity_score}
                        for r in reviews]}


# ----------------------- FRAUD -----------------------
@router.get("/api/fraud/scan", tags=["fraud"])
def fraud_scan(db: Session = Depends(get_db), min_risk: float = 50):
    orch = Orchestrator(db)
    data = orch.fraud_pass()
    flagged = [{"seller_id": sid, **info}
               for sid, info in data["per_seller"].items()
               if info["risk"] >= min_risk]
    flagged.sort(key=lambda x: -x["risk"])
    # attach names + location for the fraud map
    for f in flagged:
        s = db.query(models.Seller).get(f["seller_id"])
        if s:
            f["name"], f["state"], f["lat"], f["lng"] = s.name, s.state, s.lat, s.lng
    return {"flagged_count": len(flagged), "sellers": flagged}


@router.get("/api/fraud/map", tags=["fraud"])
def fraud_map(db: Session = Depends(get_db)):
    """Aggregated fraud risk by state for the heatmap."""
    orch = Orchestrator(db)
    data = orch.fraud_pass()
    by_state = {}
    for sid, info in data["per_seller"].items():
        s = db.query(models.Seller).get(sid)
        if not s:
            continue
        by_state.setdefault(s.state, {"risk_sum": 0, "count": 0, "high": 0})
        by_state[s.state]["risk_sum"] += info["risk"]
        by_state[s.state]["count"] += 1
        if info["risk"] >= 50:
            by_state[s.state]["high"] += 1
    out = [{"state": k, "avg_risk": round(v["risk_sum"] / v["count"], 1),
            "high_risk_sellers": v["high"], "total": v["count"]}
           for k, v in by_state.items()]
    out.sort(key=lambda x: -x["avg_risk"])
    return out


# ----------------------- RETURNS / PREDICTION -----------------------
@router.post("/api/returns/predict", tags=["returns"])
def predict_return(req: schemas.ReturnPredictRequest, db: Session = Depends(get_db)):
    seller = db.query(models.Seller).get(req.seller_id)
    product = db.query(models.Product).get(req.product_id)
    if not seller or not product:
        raise HTTPException(404, "Seller or product not found")
    avg = db.query(func.avg(models.Product.price)).filter(
        models.Product.category == product.category).scalar() or 0
    res = ReturnPredictionAgent().run(
        seller=seller, product=product,
        delivery_days=req.delivery_days, category_avg_price=avg)
    return res.dict()


# ----------------------- PRICE -----------------------
@router.post("/api/price/recommend", tags=["price"])
def recommend_price(req: schemas.PriceRequest, db: Session = Depends(get_db)):
    product = db.query(models.Product).get(req.product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    prices = [r[0] for r in db.query(models.Product.price).filter(
        models.Product.category == product.category).all() if r[0]]
    res = PriceIntelligenceAgent().run(product, prices)
    return res.dict()


# ----------------------- LOGISTICS -----------------------
@router.post("/api/logistics/optimize", tags=["logistics"])
def optimize_logistics(req: schemas.LogisticsRequest):
    res = LogisticsOptimizationAgent().run(dest_lat=req.dest_lat, dest_lng=req.dest_lng)
    return res.dict()


# ----------------------- SUPPORT -----------------------
@router.post("/api/support/ask", tags=["support"])
def support_ask(req: schemas.SupportRequest, db: Session = Depends(get_db)):
    order = db.query(models.Order).get(req.order_id) if req.order_id else None
    res = CustomerSupportAgent().run(message=req.message, lang=req.lang, order=order)
    return res.dict()


# ----------------------- ANALYTICS -----------------------
@router.get("/api/analytics/overview", tags=["analytics"])
def analytics_overview(db: Session = Depends(get_db)):
    sellers = db.query(func.count(models.Seller.id)).scalar()
    products = db.query(func.count(models.Product.id)).scalar()
    orders = db.query(func.count(models.Order.id)).scalar()
    returns = db.query(func.count(models.Return.id)).scalar()
    complaints = db.query(func.count(models.Complaint.id)).scalar()
    return_rate = round(returns / orders * 100, 1) if orders else 0

    # marketplace health = blend of inverse return rate, fraud, complaints
    orch = Orchestrator(db)
    fraud = orch.fraud_pass()
    avg_fraud = (sum(i["risk"] for i in fraud["per_seller"].values())
                 / max(1, len(fraud["per_seller"])))
    health = round(max(0, 100 - return_rate * 1.5 - avg_fraud * 0.5), 1)

    return {
        "sellers": sellers, "products": products, "orders": orders,
        "returns": returns, "complaints": complaints,
        "return_rate_pct": return_rate,
        "avg_fraud_risk": round(avg_fraud, 1),
        "flagged_sellers": fraud["flagged_count"],
        "marketplace_health": health,
    }


@router.get("/api/analytics/returns-by-category", tags=["analytics"])
def returns_by_category(db: Session = Depends(get_db)):
    rows = (db.query(models.Product.category, func.count(models.Return.id))
            .join(models.Order, models.Order.product_id == models.Product.id)
            .join(models.Return, models.Return.order_id == models.Order.id)
            .group_by(models.Product.category).all())
    return [{"category": c, "returns": n} for c, n in rows]


@router.get("/api/analytics/orders-by-status", tags=["analytics"])
def orders_by_status(db: Session = Depends(get_db)):
    rows = (db.query(models.Order.status, func.count(models.Order.id))
            .group_by(models.Order.status).all())
    return [{"status": s, "count": n} for s, n in rows]


@router.get("/api/analytics/seller-ranking", tags=["analytics"])
def seller_ranking(db: Session = Depends(get_db), limit: int = 10):
    """Live trust ranking across a sample of sellers."""
    orch = Orchestrator(db)
    sample = db.query(models.Seller).limit(40).all()
    scored = []
    for s in sample:
        r = orch.evaluate_seller(s.id, persist=False)
        scored.append({"seller_id": s.id, "name": s.name,
                       "overall": r["overall"], "band": r["band"]})
    scored.sort(key=lambda x: -x["overall"])
    return {"top": scored[:limit], "bottom": scored[-limit:][::-1]}


@router.get("/api/agents/activity", tags=["agents"])
def agents_activity(db: Session = Depends(get_db)):
    """Live agent activity feed (runs a quick orchestrated pass)."""
    orch = Orchestrator(db)
    orch.fraud_pass()
    for s in db.query(models.Seller).limit(5).all():
        orch.evaluate_seller(s.id, persist=False)
    return {"activity": orch.activity_log()[-25:]}
