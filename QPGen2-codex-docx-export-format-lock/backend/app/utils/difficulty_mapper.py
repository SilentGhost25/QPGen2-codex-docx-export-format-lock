"""
Derive difficulty automatically from Bloom's Taxonomy level.

Maps RBT levels (L1–L6) to difficulty tiers so the backend never
depends on the frontend passing a difficulty value.
"""

from __future__ import annotations

from typing import Any

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


def safe_question_payload(question: Any) -> dict:
    """Normalise a raw question dict or object into a safe, serialisable payload.

    Ensures ``difficulty`` is always present and derived from Bloom level.
    """
    def qget(field: str, default: Any = None) -> Any:
        if isinstance(question, dict):
            return question.get(field, default)
        return getattr(question, field, default)

    bloom = (
        qget("bloom_level")
        or qget("bloom")
        or qget("rbt_level")
        or "L3"
    )
    return {
        "question_text": (qget("text") or qget("question_text") or "").strip(),
        "marks": int(qget("marks", 0)),
        "co": qget("course_outcome") or qget("co") or "CO1",
        "bloom": bloom,
        "difficulty": derive_difficulty(bloom),
    }
