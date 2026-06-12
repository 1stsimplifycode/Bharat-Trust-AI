"""
Price Intelligence Agent.

Recommends an optimal price using category statistics and a simple
price-elasticity heuristic. Given the distribution of competitor prices in
the same category, it nudges toward a competitive band and estimates the
expected change in unit sales.
"""
import statistics
from .base import BaseAgent, AgentResult


class PriceIntelligenceAgent(BaseAgent):
    name = "price_intelligence"

    # assumed elasticity: 1% price drop -> ELASTICITY% sales rise
    ELASTICITY = 1.6

    def run(self, product, category_prices) -> AgentResult:
        prices = [p for p in category_prices if p > 0]
        if len(prices) < 3:
            return AgentResult(
                agent=self.name, score=product.price,
                reasons=["Insufficient category data"],
                data={"recommended_price": product.price, "expected_sales_change_pct": 0},
            )

        median = statistics.median(prices)
        p25 = statistics.quantiles(prices, n=4)[0]
        p75 = statistics.quantiles(prices, n=4)[2]

        current = product.price
        # target the competitive sweet spot: a bit below median if currently high
        if current > p75:
            target = round((median + p75) / 2, -1) or median
            note = "Priced above 75th percentile — lowering to competitive band"
        elif current < p25:
            target = round((p25 + median) / 2, -1) or median
            note = "Priced below market — room to raise without losing demand"
        else:
            target = round(current * 0.98, -1) or current
            note = "Already competitive — minor optimization only"

        # Keep the recommendation actionable: never suggest a move larger than
        # ±35% from the current price in a single step (avoids absurd jumps when
        # a listing sits far from its category band).
        lo, hi = current * 0.65, current * 1.35
        target = round(max(lo, min(hi, target)), -1) or current

        pct_change = (target - current) / current * 100 if current else 0
        # realistic elasticity response, clamped to a sane band
        expected_sales_change = round(max(-50.0, min(50.0, -pct_change * self.ELASTICITY)), 1)

        return AgentResult(
            agent=self.name,
            score=target,
            reasons=[note, f"Category median ₹{median:.0f}"],
            data={
                "current_price": current,
                "recommended_price": target,
                "category_median": round(median, 0),
                "expected_sales_change_pct": expected_sales_change,
            },
        )
