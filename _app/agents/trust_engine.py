"""
Trust Score Engine.

Fuses the six component signals into an overall 0..100 marketplace trust
score for a seller, with transparent weights and aggregated reasoning.
Fraud is inverted (high fraud risk lowers trust).
"""
from .base import clamp

WEIGHTS = {
    "seller": 0.25,
    "fraud": 0.25,       # uses (100 - fraud_risk)
    "return": 0.12,      # uses (100 - return_risk)
    "authenticity": 0.16,
    "review": 0.12,
    "delivery": 0.10,
}


def compute_overall(*, seller_score, fraud_risk, return_risk,
                    authenticity, review_score, delivery_score):
    fraud_trust = 100 - fraud_risk
    return_trust = 100 - return_risk
    overall = (
        WEIGHTS["seller"] * seller_score
        + WEIGHTS["fraud"] * fraud_trust
        + WEIGHTS["return"] * return_trust
        + WEIGHTS["authenticity"] * authenticity
        + WEIGHTS["review"] * review_score
        + WEIGHTS["delivery"] * delivery_score
    )
    return round(clamp(overall), 1)


def band(score):
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Fair"
    if score >= 35:
        return "Poor"
    return "High Risk"
