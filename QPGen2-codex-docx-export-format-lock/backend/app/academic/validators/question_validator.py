from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..planning.blueprint_engine import QuestionTask
from ..policies import validate_co_rbt_alignment

# ---------------------------------------------------------------------------
# Synthetic / placeholder terms that indicate hallucinated or filler content.
# Any question whose text contains one of these (case-insensitive) is REJECTED.
# ---------------------------------------------------------------------------
_HALLUCINATION_TERMS: tuple[str, ...] = (
    "syllabus concepts",
    "topic outcome",
    "fundamental concepts",
    "course outcomes",
    "learning objectives",
    "module topics",
    "uploaded academic material",
    "provided context",
    "source_indices",
    "concepts of the subject",
    "topics covered in the module",
    "as per syllabus",
    "key concepts",
    "important topics",
)


@dataclass
class QuestionValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_question_object(text: str, task: QuestionTask) -> QuestionValidation:
    errors: list[str] = []
    warnings: list[str] = []
    normalized = " ".join(str(text or "").split())

    if len(normalized) < 18:
        errors.append("Question text is too short")
    if any(token in normalized.lower() for token in _HALLUCINATION_TERMS):
        errors.append("Question contains synthetic filler / placeholder text — rejected")
    if not validate_co_rbt_alignment(task.co, task.rbt):
        errors.append(f"{task.co} is not allowed to use {task.rbt}")
    if task.marks >= 8 and len(normalized.split()) < 6:
        warnings.append("High-mark question may be too shallow")

    return QuestionValidation(ok=not errors, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# Standalone grounding check (used at question-assembly time, not LLM time).
# Accepts any dict-like question object (DB row, Pydantic model .model_dump(),
# or plain dict coming from the generation pipeline).
# ---------------------------------------------------------------------------

def validate_grounding(question: Any) -> QuestionValidation:
    """
    Hard grounding guard.

    Rules (all must pass for ok=True):
      1. Question text must not contain any hallucination / placeholder term.
      2. source_chunk_id must be non-None (proves the question was retrieved,
         not fabricated from templates).
      3. Question text must be at least 20 characters long.

    Returns a QuestionValidation instance.  Callers should drop (not include)
    any question where ok is False.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # Normalise — works for dicts, SQLAlchemy ORM rows, and Pydantic models
    if hasattr(question, "model_dump"):
        q = question.model_dump()
    elif hasattr(question, "__dict__"):
        q = vars(question)
    else:
        q = dict(question) if hasattr(question, "__iter__") else {}

    text: str = " ".join(str(q.get("text") or q.get("question_text", "")).split())

    # Rule 1 — minimum length
    if len(text) < 20:
        errors.append("Question text is too short (< 20 chars)")

    # Rule 2 — no synthetic filler
    text_lower = text.lower()
    matched = [t for t in _HALLUCINATION_TERMS if t in text_lower]
    if matched:
        errors.append(
            f"Question rejected: contains synthetic placeholder(s): {matched}"
        )

    # Rule 3 — source_chunk_id must be present
    chunk_id = q.get("source_chunk_id") or q.get("chunk_id")
    if chunk_id is None:
        errors.append(
            "Question rejected: source_chunk_id is None — not grounded to any retrieved chunk"
        )

    if len(text.split()) < 5:
        warnings.append("Question text is very short — verify it is complete")

    return QuestionValidation(ok=not errors, errors=errors, warnings=warnings)

