"""
Derive difficulty automatically from Bloom's Taxonomy level.

Maps RBT levels (L1–L6) to difficulty tiers so the backend never
depends on the frontend passing a difficulty value.
"""

from __future__ import annotations

BLOOM_DIFFICULTY_MAP: dict[str, str] = {
    "L1": "easy",
    "L2": "easy",
    "L3": "medium",
    "L4": "medium",
    "L5": "hard",
    "L6": "hard",
}


def derive_difficulty(bloom_level: str | None) -> str:
    """Return a difficulty string derived from the given Bloom level.

    Falls back to ``"medium"`` when the level is unknown or ``None``.
    """
    if not bloom_level:
        return "medium"
    return BLOOM_DIFFICULTY_MAP.get(str(bloom_level).strip().upper(), "medium")


def safe_question_payload(question: dict) -> dict:
    """Normalise a raw question dict into a safe, serialisable payload.

    Ensures ``difficulty`` is always present and derived from Bloom level.
    """
    bloom = (
        question.get("bloom_level")
        or question.get("bloom")
        or question.get("rbt_level")
        or "L3"
    )
    return {
        "question_text": (question.get("text") or question.get("question_text") or "").strip(),
        "marks": int(question.get("marks", 0)),
        "co": question.get("course_outcome") or question.get("co") or "CO1",
        "bloom": bloom,
        "difficulty": derive_difficulty(bloom),
    }
