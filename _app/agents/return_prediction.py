"""
Return Prediction Agent.

Estimates P(return) for an order BEFORE shipment using a transparent
logistic model over interpretable features. Coefficients are hand-calibrated
(could be swapped for a trained LogisticRegression on historical returns).

Outputs probability, the dominant reason, and a suggested intervention.
"""
import math
from .base import BaseAgent, AgentResult


class ReturnPredictionAgent(BaseAgent):
    name = "return_prediction"

    # logistic coefficients on standardized-ish features
    BIAS = -2.1
    COEF = {
        "seller_cancel": 2.4,      # seller cancellation_rate (0..1)
        "delivery_days": 0.12,     # per day
        "low_rating": 1.6,         # (5 - avg_rating)/5 normalized
        "high_price": 0.6,         # price / category_avg - 1, clipped
        "category_risk": 1.0,      # category base propensity 0..1
        "complaint_ratio": 1.8,
    }

    # apparel & electronics return more; staples return less
    CATEGORY_RISK = {
        "Apparel": 0.45, "Footwear": 0.40, "Electronics": 0.30,
        "Accessories": 0.28, "Beauty": 0.22, "Home": 0.18,
        "Kitchen": 0.15, "Grocery": 0.08, "Books": 0.06,
    }

    def predict(self, *, seller, product, delivery_days, category_avg_price) -> dict:
        orders = max(1, seller.total_orders)
        complaint_ratio = seller.complaint_count / orders
        low_rating = max(0.0, (5 - (product.avg_rating or 3.5)) / 5)
        price_ratio = 0.0
        if category_avg_price > 0:
            price_ratio = max(-0.5, min(1.5, product.price / category_avg_price - 1))
        cat_risk = self.CATEGORY_RISK.get(product.category, 0.2)

        z = (
            self.BIAS
            + self.COEF["seller_cancel"] * seller.cancellation_rate
            + self.COEF["delivery_days"] * delivery_days
            + self.COEF["low_rating"] * low_rating
            + self.COEF["high_price"] * max(0, price_ratio)
            + self.COEF["category_risk"] * cat_risk
            + self.COEF["complaint_ratio"] * complaint_ratio
        )
        prob = 1 / (1 + math.exp(-z))

        # dominant reason = largest positive contribution
        contribs = {
            "Seller has elevated cancellations": self.COEF["seller_cancel"] * seller.cancellation_rate,
            "Long delivery window": self.COEF["delivery_days"] * delivery_days,
            "Low product rating": self.COEF["low_rating"] * low_rating,
            "Priced above category average": self.COEF["high_price"] * max(0, price_ratio),
            f"{product.category} is a high-return category": self.COEF["category_risk"] * cat_risk,
            "Seller complaint history": self.COEF["complaint_ratio"] * complaint_ratio,
        }
        reason = max(contribs, key=contribs.get)

        if prob > 0.5:
            intervention = "Add sizing/quality info + proactive QC call before dispatch"
        elif prob > 0.3:
            intervention = "Attach detailed product imagery and confirm address"
        else:
            intervention = "No intervention needed"

        return {
            "return_probability": round(prob, 3),
            "reason": reason,
            "intervention": intervention,
        }

    def run(self, *, seller, product, delivery_days, category_avg_price) -> AgentResult:
        out = self.predict(
            seller=seller, product=product,
            delivery_days=delivery_days, category_avg_price=category_avg_price,
        )
        return AgentResult(
            agent=self.name,
            score=out["return_probability"] * 100,
            reasons=[out["reason"], out["intervention"]],
            data=out,
        )
