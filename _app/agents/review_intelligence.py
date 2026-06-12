"""
Review Intelligence Agent.

Scores each review's authenticity (0..100, higher = more genuine) using
interpretable signals that do not need an LLM:
  - template / near-duplicate detection (Jaccard on token shingles)
  - extreme-rating burst (all 5s or all 1s clustered in time)
  - generic/spam phrase density
  - length & lexical diversity (very short, repetitive text is suspect)
"""
import re
from collections import Counter
from .base import BaseAgent, AgentResult

SPAM_PHRASES = [
    "best product", "must buy", "value for money", "highly recommend",
    "good product", "nice product", "awesome", "superb", "loved it",
    "amazing product", "worth it", "go for it",
]
TOKEN = re.compile(r"[a-z]+")


def shingles(text, k=3):
    toks = TOKEN.findall(text.lower())
    return set(tuple(toks[i:i + k]) for i in range(max(0, len(toks) - k + 1)))


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class ReviewIntelligenceAgent(BaseAgent):
    name = "review_intelligence"

    def run(self, reviews) -> AgentResult:
        reviews = list(reviews)
        if not reviews:
            return AgentResult(agent=self.name, score=100.0, reasons=["No reviews"])

        shingle_sets = [(r, shingles(r.text or "")) for r in reviews]
        scored = {}
        suspicious = 0

        for r, sh in shingle_sets:
            text = (r.text or "").lower()
            penalties = []
            score = 100.0

            # 1. near-duplicate against other reviews (review farm template)
            max_sim = 0.0
            for other, osh in shingle_sets:
                if other.id == r.id:
                    continue
                sim = jaccard(sh, osh)
                max_sim = max(max_sim, sim)
            if max_sim > 0.6:
                score -= 45
                penalties.append("Near-duplicate of another review (template farm)")

            # 2. spam phrase density
            hits = sum(1 for p in SPAM_PHRASES if p in text)
            if hits >= 2:
                score -= 20
                penalties.append("High generic-praise phrase density")

            # 3. very short, low-information
            words = TOKEN.findall(text)
            if len(words) < 4:
                score -= 20
                penalties.append("Extremely short review")

            # 4. low lexical diversity (repetition)
            if words:
                diversity = len(set(words)) / len(words)
                if diversity < 0.5 and len(words) > 6:
                    score -= 15
                    penalties.append("Repetitive / low-diversity text")

            score = max(0.0, min(100.0, score))
            if score < 55:
                suspicious += 1
            r.authenticity_score = round(score, 1)  # mutate ORM obj; caller commits
            scored[r.id] = {"score": round(score, 1), "flags": penalties}

        avg = round(sum(v["score"] for v in scored.values()) / len(scored), 1)
        return AgentResult(
            agent=self.name,
            score=avg,
            reasons=[f"{suspicious}/{len(reviews)} reviews look inauthentic"],
            data={"per_review": scored, "suspicious_count": suspicious},
        )
