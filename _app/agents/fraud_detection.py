"""
Fraud Detection Agent.

Two real techniques combined:
  1. Graph / identity duplication: GST, phone and IP shared across distinct
     sellers indicates colluding or sock-puppet accounts.
  2. Behavioural anomaly detection over feature vectors (cancellation, delay,
     complaints, volatility, review velocity).

For (2) the agent prefers scikit-learn's Isolation Forest. On machines where
compiled DLLs are blocked (e.g. Windows Smart App Control / App Control
policies block scipy's unsigned binaries), it transparently degrades to a
pure-Python robust z-score detector (median/MAD) with the same interface and
output range — so the platform runs anywhere Python runs, with zero compiled
dependencies on the fallback path.

Returns a per-seller fraud risk in 0..100 (higher = riskier) plus the
specific evidence that triggered it.
"""
import os
import statistics
from collections import defaultdict

from .base import BaseAgent, AgentResult, clamp

# ---- optional ML backend (graceful degradation) ----
ML_BACKEND = "robust-zscore"
if not os.getenv("BHARATTRUST_FORCE_FALLBACK"):
    try:  # pragma: no cover - environment dependent
        import numpy as _np
        from sklearn.ensemble import IsolationForest as _IsolationForest
        ML_BACKEND = "isolation-forest"
    except Exception:  # ImportError or blocked-DLL OSError
        ML_BACKEND = "robust-zscore"


class FraudDetectionAgent(BaseAgent):
    name = "fraud_detection"

    def _feature_rows(self, sellers):
        rows = []
        for s in sellers:
            orders = max(1, s.total_orders)
            rows.append([
                s.cancellation_rate,
                s.avg_delivery_delay_days,
                s.complaint_count / orders,
                s.price_volatility,
                s.review_velocity,
            ])
        return rows

    # ---------- anomaly scorers (both return list of 0..1 floats) ----------
    def _anomaly_isolation_forest(self, rows):
        X = _np.array(rows, dtype=float)
        mu, sigma = X.mean(axis=0), X.std(axis=0) + 1e-9
        Xn = (X - mu) / sigma
        iso = _IsolationForest(
            n_estimators=200, contamination=0.08, random_state=42
        ).fit(Xn)
        raw = -iso.score_samples(Xn)  # higher = more anomalous
        rmin, rmax = raw.min(), raw.max()
        return [float(v) for v in (raw - rmin) / (rmax - rmin + 1e-9)]

    def _anomaly_robust_zscore(self, rows):
        """Pure-Python fallback: per-feature robust z (median / MAD), averaged
        with caps, then min-max normalised across the population — mirrors the
        Isolation Forest output range so downstream logic is unchanged."""
        n, m = len(rows), len(rows[0])
        cols = [[rows[i][j] for i in range(n)] for j in range(m)]
        med = [statistics.median(c) for c in cols]
        mad = []
        for j, c in enumerate(cols):
            mad.append(statistics.median(abs(x - med[j]) for x in c) or 1e-9)
        raw = []
        for i in range(n):
            zs = []
            for j in range(m):
                z = abs(rows[i][j] - med[j]) / (1.4826 * mad[j])
                zs.append(min(z / 4.0, 1.0))  # cap each feature's influence
            raw.append(sum(zs) / m)
        rmin, rmax = min(raw), max(raw)
        span = (rmax - rmin) or 1e-9
        return [(v - rmin) / span for v in raw]

    def run(self, sellers) -> AgentResult:
        sellers = list(sellers)
        if not sellers:
            return AgentResult(agent=self.name, score=0.0)

        # ---- 1. Duplicate identity graph ----
        by_gst, by_phone, by_ip = defaultdict(list), defaultdict(list), defaultdict(list)
        for s in sellers:
            if s.gst_number:
                by_gst[s.gst_number].append(s.id)
            if s.phone:
                by_phone[s.phone].append(s.id)
            if s.ip_address:
                by_ip[s.ip_address].append(s.id)

        dup_flags = defaultdict(list)  # seller_id -> [evidence]
        for field, table in (("GST", by_gst), ("phone", by_phone), ("IP", by_ip)):
            for value, ids in table.items():
                if len(ids) > 1:
                    for sid in ids:
                        others = [i for i in ids if i != sid]
                        dup_flags[sid].append(
                            f"Shared {field} with seller(s) {others}"
                        )

        # ---- 2. Behavioural anomaly score (sklearn or pure-Python) ----
        rows = self._feature_rows(sellers)
        if ML_BACKEND == "isolation-forest":
            anomaly = self._anomaly_isolation_forest(rows)
        else:
            anomaly = self._anomaly_robust_zscore(rows)

        results = {}
        flagged = 0
        for i, s in enumerate(sellers):
            reasons = []
            risk = anomaly[i] * 60  # anomaly contributes up to 60 pts
            if anomaly[i] > 0.7:
                reasons.append("Behavioural pattern flagged as statistical outlier")

            dup_evidence = dup_flags.get(s.id, [])
            if dup_evidence:
                risk += min(40, 18 * len(dup_evidence))  # each dup adds risk
                reasons.extend(dup_evidence)

            # concrete behaviour callouts
            if s.cancellation_rate > 0.25:
                reasons.append("Excessive cancellations")
            if s.review_velocity > 18:
                reasons.append("Possible review farm (velocity spike)")

            risk = float(clamp(risk))
            if risk >= 50:
                flagged += 1
            results[s.id] = {
                "risk": round(risk, 1),
                "anomaly": round(float(anomaly[i]), 3),
                "duplicates": dup_evidence,
                "reasons": reasons[:5],
            }

        avg_risk = round(
            sum(r["risk"] for r in results.values()) / len(results), 1
        )
        return AgentResult(
            agent=self.name,
            score=avg_risk,
            reasons=[f"{flagged} sellers flagged at >=50 risk ({ML_BACKEND})"],
            data={"per_seller": results, "flagged_count": flagged,
                  "backend": ML_BACKEND},
        )
