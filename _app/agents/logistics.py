"""
Logistics Optimization Agent.

Chooses the nearest fulfilment warehouse to the destination, picks a courier
by distance band, and computes ETA + cost vs a naive single-hub baseline to
report real savings. Distances use the haversine formula over real city
coordinates.
"""
from .base import BaseAgent, AgentResult, haversine_km

# A small national warehouse network (lat, lng)
WAREHOUSES = {
    "Bengaluru WH": (12.9716, 77.5946),
    "Mumbai WH": (19.0760, 72.8777),
    "Delhi WH": (28.7041, 77.1025),
    "Kolkata WH": (22.5726, 88.3639),
    "Hyderabad WH": (17.3850, 78.4867),
}
# naive baseline always ships from a single central hub (Nagpur ~ centre)
CENTRAL_HUB = (21.1458, 79.0882)

COURIERS = [
    ("Local Express", 300, 12.0, 1.0),    # name, max_km, rate/km, base_days
    ("Regional Logistics", 900, 9.0, 2.0),
    ("National Freight", 99999, 6.5, 3.5),
]


class LogisticsOptimizationAgent(BaseAgent):
    name = "logistics"

    def _courier_for(self, dist):
        for name, max_km, rate, base_days in COURIERS:
            if dist <= max_km:
                return name, rate, base_days
        return COURIERS[-1][0], COURIERS[-1][2], COURIERS[-1][3]

    def _cost_eta(self, dist):
        name, rate, base_days = self._courier_for(dist)
        cost = round(40 + dist * rate / 10, 0)   # handling + distance cost
        eta = round(base_days + dist / 500, 1)
        return name, cost, eta

    def run(self, *, dest_lat, dest_lng) -> AgentResult:
        # optimized: nearest warehouse
        best_wh, best_dist = None, float("inf")
        for wh, (lat, lng) in WAREHOUSES.items():
            d = haversine_km(lat, lng, dest_lat, dest_lng)
            if d < best_dist:
                best_wh, best_dist = wh, d
        courier, cost, eta = self._cost_eta(best_dist)

        # baseline: central hub, national freight
        base_dist = haversine_km(*CENTRAL_HUB, dest_lat, dest_lng)
        _, base_cost, base_eta = self._cost_eta(base_dist)
        savings = round(max(0, base_cost - cost), 0)

        return AgentResult(
            agent=self.name,
            score=savings,
            reasons=[
                f"Fulfil from {best_wh} ({best_dist:.0f} km) via {courier}",
                f"Saves ₹{savings:.0f} and {max(0, base_eta - eta):.1f} days vs central hub",
            ],
            data={
                "warehouse": best_wh,
                "courier": courier,
                "distance_km": round(best_dist, 0),
                "eta_days": eta,
                "cost": cost,
                "baseline_cost": base_cost,
                "savings": savings,
            },
        )
