"""
Agent Orchestrator.

Central coordinator. Runs the specialized agents in the right order, threads
their structured outputs through a shared-memory dict, and produces the final
fused TrustScore + an activity log (used by the live "AI agent activity"
monitor in the UI). This is the LangGraph/CrewAI-style brain, implemented
without external dependencies so it runs fully offline.
"""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from .. import models
from .seller_monitoring import SellerMonitoringAgent
from .fraud_detection import FraudDetectionAgent
from .return_prediction import ReturnPredictionAgent
from .review_intelligence import ReviewIntelligenceAgent
from .price_intelligence import PriceIntelligenceAgent
from .logistics import LogisticsOptimizationAgent
from .authenticity import ProductAuthenticityAgent
from .support import CustomerSupportAgent
from . import trust_engine


class Orchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.memory: dict = {}
        self.activity: list = []
        self.seller_agent = SellerMonitoringAgent()
        self.fraud_agent = FraudDetectionAgent()
        self.return_agent = ReturnPredictionAgent()
        self.review_agent = ReviewIntelligenceAgent()
        self.price_agent = PriceIntelligenceAgent()
        self.logistics_agent = LogisticsOptimizationAgent()
        self.auth_agent = ProductAuthenticityAgent()
        self.support_agent = CustomerSupportAgent()

    def _log(self, agent, summary):
        self.activity.append({
            "agent": agent,
            "summary": summary,
            "at": datetime.utcnow().isoformat(timespec="seconds"),
        })

    # ---- marketplace-wide fraud pass (run once, cached in memory) ----
    def fraud_pass(self):
        if "fraud" in self.memory:
            return self.memory["fraud"]
        sellers = self.db.query(models.Seller).all()
        res = self.fraud_agent.run(sellers)
        self.memory["fraud"] = res.data
        self._log("fraud_detection", res.reasons[0] if res.reasons else "fraud scan complete")
        return res.data

    def _category_avg_price(self, category):
        rows = (self.db.query(models.Product.price)
                .filter(models.Product.category == category).all())
        prices = [r[0] for r in rows if r[0]]
        return sum(prices) / len(prices) if prices else 0.0

    # ---- full per-seller evaluation, persisted as TrustScore ----
    def evaluate_seller(self, seller_id: int, persist=True) -> dict:
        seller = self.db.query(models.Seller).get(seller_id)
        if not seller:
            return {"error": "seller not found"}

        # 1. seller monitoring
        sm = self.seller_agent.run(seller)
        self._log("seller_monitoring", f"{seller.name}: trust {sm.score:.0f}")

        # 2. fraud (from marketplace pass)
        fraud_data = self.fraud_pass()
        fr = fraud_data["per_seller"].get(seller.id, {"risk": 0, "reasons": []})

        # 3. reviews for this seller's products
        product_ids = [p.id for p in seller.products]
        reviews = (self.db.query(models.Review)
                   .filter(models.Review.product_id.in_(product_ids)).all()
                   if product_ids else [])
        rv = self.review_agent.run(reviews)
        if persist and reviews:
            self.db.commit()  # persist authenticity_score mutations
        self._log("review_intelligence", rv.reasons[0] if rv.reasons else "reviews scored")

        # 4. authenticity (avg across products) + return risk (avg across products)
        auth_scores, return_risks = [], []
        for p in seller.products[:50]:
            a = self.auth_agent.run(p, seller)
            auth_scores.append(a.score)
            rp = self.return_agent.predict(
                seller=seller, product=p, delivery_days=4,
                category_avg_price=self._category_avg_price(p.category),
            )
            return_risks.append(rp["return_probability"] * 100)
        authenticity = sum(auth_scores) / len(auth_scores) if auth_scores else 70.0
        return_risk = sum(return_risks) / len(return_risks) if return_risks else 20.0

        # 5. delivery sub-score reuse
        delivery_score = sm.data["subscores"]["delivery"]

        overall = trust_engine.compute_overall(
            seller_score=sm.score, fraud_risk=fr["risk"], return_risk=return_risk,
            authenticity=authenticity, review_score=rv.score, delivery_score=delivery_score,
        )

        reasons = sm.reasons + fr.get("reasons", [])[:2]
        result = {
            "seller_id": seller.id,
            "seller_name": seller.name,
            "overall": overall,
            "band": trust_engine.band(overall),
            "components": {
                "seller": round(sm.score, 1),
                "fraud_risk": round(fr["risk"], 1),
                "return_risk": round(return_risk, 1),
                "authenticity": round(authenticity, 1),
                "review": round(rv.score, 1),
                "delivery": round(delivery_score, 1),
            },
            "reasons": reasons,
        }

        if persist:
            ts = models.TrustScore(
                seller_id=seller.id, seller_score=sm.score, fraud_score=fr["risk"],
                return_score=return_risk, authenticity_score=authenticity,
                review_score=rv.score, delivery_score=delivery_score,
                overall=overall, reasoning=json.dumps(reasons),
            )
            self.db.add(ts)
            self.db.commit()

        self._log("trust_engine", f"{seller.name}: overall {overall} ({result['band']})")
        return result

    def activity_log(self):
        return self.activity
