"""
Seller Monitoring Agent.

Computes a 0-100 Seller Trust Score from behavioural signals and emits
human-readable reasoning for each contributing factor. Pure deterministic
scoring — no external calls — so it runs identically offline.
"""
from .base import BaseAgent, AgentResult, clamp


class SellerMonitoringAgent(BaseAgent):
    name = "seller_monitoring"

    # weights sum to 1.0
    W = {
        "cancellation": 0.22,
        "delivery": 0.20,
        "complaints": 0.20,
        "pricing": 0.15,
        "reviews": 0.13,
        "verification": 0.10,
    }

    def run(self, seller) -> AgentResult:
        reasons = []

        # 1. Cancellation rate (0..1) -> sub-score 0..100
        cancel = clamp((1 - seller.cancellation_rate) * 100)
        if seller.cancellation_rate < 0.05:
            reasons.append(f"Low cancellation rate ({seller.cancellation_rate:.0%})")
        elif seller.cancellation_rate > 0.20:
            reasons.append(f"High cancellation rate ({seller.cancellation_rate:.0%}) hurts reliability")

        # 2. Delivery delay (days) -> degrade after 1 day, floor at 5 days
        delay = seller.avg_delivery_delay_days
        delivery = clamp(100 - (max(0, delay - 1) / 4) * 100)
        if delay <= 1:
            reasons.append("On-time delivery history")
        elif delay >= 3:
            reasons.append(f"Average delivery delayed by {delay:.1f} days")

        # 3. Complaints relative to order volume
        orders = max(1, seller.total_orders)
        complaint_ratio = seller.complaint_count / orders
        complaints = clamp(100 - complaint_ratio * 500)  # 20% complaints -> 0
        if complaint_ratio < 0.02:
            reasons.append("Very few complaints per order")
        elif complaint_ratio > 0.08:
            reasons.append(f"Elevated complaint ratio ({complaint_ratio:.1%})")

        # 4. Price stability (volatility std/mean) -> lower is better
        pricing = clamp(100 - seller.price_volatility * 200)
        if seller.price_volatility < 0.05:
            reasons.append("Stable, predictable pricing")
        elif seller.price_volatility > 0.25:
            reasons.append("Volatile pricing detected (possible manipulation)")

        # 5. Review velocity spikes are suspicious (handled deeper by fraud agent)
        reviews = clamp(100 - max(0, seller.review_velocity - 5) * 8)
        if seller.review_velocity > 15:
            reasons.append("Abnormal spike in review volume")

        # 6. Verified invoices
        verification = 100.0 if seller.verified_invoices else 55.0
        if seller.verified_invoices:
            reasons.append("Verified invoices on file")
        else:
            reasons.append("Invoices not verified")

        score = (
            self.W["cancellation"] * cancel
            + self.W["delivery"] * delivery
            + self.W["complaints"] * complaints
            + self.W["pricing"] * pricing
            + self.W["reviews"] * reviews
            + self.W["verification"] * verification
        )

        return AgentResult(
            agent=self.name,
            score=clamp(score),
            reasons=reasons[:5],
            data={
                "subscores": {
                    "cancellation": round(cancel, 1),
                    "delivery": round(delivery, 1),
                    "complaints": round(complaints, 1),
                    "pricing": round(pricing, 1),
                    "reviews": round(reviews, 1),
                    "verification": round(verification, 1),
                }
            },
        )
