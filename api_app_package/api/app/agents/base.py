"""
Base agent + shared helpers.

Every agent returns a structured dict:
    {"agent": str, "score": float, "reasons": [str], "data": {...}}
so the orchestrator can merge them into shared memory uniformly.
"""
import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    agent: str
    score: float = 0.0
    reasons: list = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "score": round(self.score, 2),
            "reasons": self.reasons,
            "data": self.data,
        }


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def haversine_km(lat1, lng1, lat2, lng2) -> float:
    """Great-circle distance between two points in km."""
    if None in (lat1, lng1, lat2, lng2):
        return 1500.0  # conservative national default
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class BaseAgent:
    name = "base"

    def run(self, *args, **kwargs) -> AgentResult:  # pragma: no cover - interface
        raise NotImplementedError
