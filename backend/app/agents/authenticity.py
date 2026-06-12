"""
Product Authenticity Agent.

Without paid OCR/vision APIs this implements a real, transparent heuristic
over verifiable metadata: presence of QR + invoice, brand-vs-price coherence
(suspiciously cheap branded goods = likely counterfeit), description quality,
and seller verification. Returns an authenticity score and counterfeit
probability with reasons. The interface is OCR-ready: pass `ocr_text` and
`brand_keywords` once a vision pipeline is wired in.
"""
from .base import BaseAgent, AgentResult, clamp

# rough "genuine" price floor as fraction of MRP per premium brand
PREMIUM_BRANDS = {"Nike", "Adidas", "Apple", "Samsung", "Sony", "Puma", "Levi's", "Boat"}


class ProductAuthenticityAgent(BaseAgent):
    name = "authenticity"

    def run(self, product, seller, ocr_text: str | None = None) -> AgentResult:
        score = 60.0
        reasons = []

        if product.has_qr:
            score += 12
            reasons.append("Scannable QR / authenticity code present")
        else:
            score -= 8
            reasons.append("No QR / authenticity code")

        if product.has_invoice:
            score += 12
            reasons.append("Tax invoice available")
        else:
            score -= 6

        if seller.verified_invoices:
            score += 8
            reasons.append("Sold by invoice-verified seller")

        # price-vs-MRP coherence for premium brands
        if product.brand in PREMIUM_BRANDS and product.mrp:
            ratio = product.price / product.mrp
            if ratio < 0.4:
                score -= 30
                reasons.append(
                    f"{product.brand} priced at {ratio:.0%} of MRP — counterfeit risk"
                )
            elif ratio < 0.6:
                score -= 12
                reasons.append("Steep discount on a premium brand — verify source")

        # description quality
        desc = (product.description or "")
        if len(desc) < 20:
            score -= 8
            reasons.append("Sparse product description")

        # OCR hook (real once vision pipeline supplies text)
        if ocr_text and product.brand and product.brand.lower() not in ocr_text.lower():
            score -= 15
            reasons.append("Brand name not found in packaging OCR")

        score = clamp(score)
        counterfeit_prob = round((100 - score) / 100, 3)
        return AgentResult(
            agent=self.name,
            score=score,
            reasons=reasons[:5],
            data={"authenticity_score": round(score, 1),
                  "counterfeit_probability": counterfeit_prob},
        )
