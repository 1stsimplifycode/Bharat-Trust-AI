"""
Customer Support Agent + Bharat Inclusion.

Rule-based intent classification routed to real actions against the database
(order tracking, refund initiation, fraud escalation). Replies can be wrapped
in a language template for 11 Indian languages — the routing/logic is
language-agnostic and the response layer is modular (voice-ready: the same
structured intent can drive a TTS layer).
"""
import re
from .base import BaseAgent, AgentResult

LANG_GREETING = {
    "en": "Here's what I found:",
    "hi": "यह जानकारी मिली:",
    "kn": "ಇಲ್ಲಿ ಮಾಹಿತಿ ಇದೆ:",
    "ta": "இதோ விவரம்:",
    "te": "ఇదిగో సమాచారం:",
    "ml": "വിവരം ഇതാ:",
    "mr": "ही माहिती मिळाली:",
    "bn": "এই তথ্য পাওয়া গেল:",
    "gu": "આ માહિતી મળી:",
    "or": "ଏହି ସୂଚନା ମିଳିଲା:",
    "pa": "ਇਹ ਜਾਣਕਾਰੀ ਮਿਲੀ:",
}

INTENTS = {
    "track": ["where", "track", "status", "delivery", "arrive", "shipped"],
    "refund": ["refund", "return", "money back", "cancel"],
    "fraud": ["fake", "counterfeit", "fraud", "scam", "duplicate"],
    "delay": ["late", "delay", "slow", "not received"],
}


class CustomerSupportAgent(BaseAgent):
    name = "support"

    def classify(self, message: str) -> str:
        m = message.lower()
        best, best_hits = "general", 0
        for intent, kws in INTENTS.items():
            hits = sum(1 for k in kws if k in m)
            if hits > best_hits:
                best, best_hits = intent, hits
        return best

    def run(self, *, message, lang="en", order=None) -> AgentResult:
        intent = self.classify(message)
        greeting = LANG_GREETING.get(lang, LANG_GREETING["en"])
        action, reply = "none", ""

        if intent == "track":
            if order:
                reply = (f"Order #{order.id} is '{order.status}', "
                         f"estimated {order.delivery_days} day(s) in transit.")
                action = "tracked_order"
            else:
                reply = "Please share your order ID to track it."
        elif intent == "refund":
            if order and order.status in ("delivered", "shipped"):
                reply = (f"Refund initiated for order #{order.id} "
                         f"(₹{order.amount:.0f}). Expect 3–5 business days.")
                action = "initiated_refund"
            else:
                reply = "Refunds apply to shipped/delivered orders. Share your order ID."
        elif intent == "fraud":
            reply = ("Flagged for our Fraud Detection Agent. A replacement or "
                     "full refund will follow verification.")
            action = "escalated_fraud"
        elif intent == "delay":
            if order:
                reply = (f"Order #{order.id} is delayed; new ETA "
                         f"{order.delivery_days} day(s). Apologies for the wait.")
                action = "explained_delay"
            else:
                reply = "Share your order ID and I'll check the delay reason."
        else:
            reply = "I can track orders, process refunds, or escalate fraud. How can I help?"

        return AgentResult(
            agent=self.name,
            score=100.0,
            reasons=[f"intent={intent}", f"action={action}"],
            data={"intent": intent, "action": action,
                  "reply": f"{greeting} {reply}", "lang": lang},
        )
