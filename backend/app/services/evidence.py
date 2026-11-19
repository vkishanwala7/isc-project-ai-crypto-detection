"""Public, deterministic evidence-interpretation rule (AI signal x provenance state).

The two dimensions are always reported separately; this only produces a readable summary.
There is deliberately NO single numeric 'truth score'."""
from __future__ import annotations

AI_TEXT = {
    "LIKELY_MANIPULATED": "the model found a manipulation signal",
    "LOW_MANIPULATION_SIGNAL": "the model found a low manipulation signal",
    "INCONCLUSIVE": "the AI result is inconclusive",
    None: "no AI analysis was run",
}


def interpret(ai: dict | None, prov_status: str | None) -> dict:
    ai_verdict = None
    ai_available = False
    if ai is not None:
        ai_available = ai.get("status") == "COMPLETED"
        ai_verdict = ai.get("verdict") if ai_available else None
        if ai_available and ai.get("reason") == "NO_FACE_DETECTED":
            ai_verdict = "INCONCLUSIVE"

    if prov_status == "TAMPERED_OR_INVALID":
        headline = "Integrity verification failed; the AI result is independent and shown separately."
        tone = "critical"
    elif prov_status == "VALID_PROVENANCE" and ai_verdict == "LOW_MANIPULATION_SIGNAL":
        headline = "Strong provenance evidence (under the local demo trust policy); the model found a low manipulation signal. Not a guarantee of authenticity."
        tone = "positive"
    elif prov_status in ("VALID_PROVENANCE", "VALID_BUT_UNTRUSTED_SIGNER") and ai_verdict == "LIKELY_MANIPULATED":
        headline = "A signed origin record exists, but AI analysis raises a manipulation signal. Inspect the editing assertions and the source workflow."
        tone = "warning"
    elif prov_status == "VALID_BUT_UNTRUSTED_SIGNER":
        headline = f"Cryptographically valid credential from a signer that is not trusted by the current policy; {AI_TEXT.get(ai_verdict)}."
        tone = "neutral"
    elif prov_status == "VALID_PROVENANCE":
        headline = f"Valid provenance under the local demo trust policy; {AI_TEXT.get(ai_verdict)}."
        tone = "positive" if ai_verdict != "LIKELY_MANIPULATED" else "warning"
    elif prov_status == "NO_PROVENANCE_FOUND" and ai_verdict == "LOW_MANIPULATION_SIGNAL":
        headline = "No origin credential found; the model found a low manipulation signal. Origin remains unverified."
        tone = "neutral"
    elif prov_status == "NO_PROVENANCE_FOUND" and ai_verdict == "LIKELY_MANIPULATED":
        headline = "No origin credential found, and the model found a manipulation signal. Treat with caution and seek corroboration; this is not proof of manipulation."
        tone = "warning"
    elif prov_status == "NO_PROVENANCE_FOUND":
        headline = f"No origin credential found; {AI_TEXT.get(ai_verdict)}. Origin remains unverified."
        tone = "neutral"
    else:
        headline = f"Provenance could not be assessed; {AI_TEXT.get(ai_verdict)}."
        tone = "neutral"

    if ai is not None and not ai_available:
        headline += " (AI model unavailable or analysis failed — no score was fabricated.)"

    return {
        "headline": headline,
        "tone": tone,
        "ai_dimension": ai_verdict or ("MODEL_UNAVAILABLE" if ai is not None and not ai_available else "NOT_RUN"),
        "provenance_dimension": prov_status or "NOT_RUN",
        "rule": "Deterministic matrix of AI verdict x provenance status (see /about#evidence). No combined truth score is computed.",
    }
