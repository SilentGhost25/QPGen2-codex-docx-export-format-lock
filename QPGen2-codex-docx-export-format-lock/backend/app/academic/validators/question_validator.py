from __future__ import annotations

from dataclasses import dataclass, field

from ..planning.blueprint_engine import QuestionTask
from ..policies import validate_co_rbt_alignment


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
    if any(token in normalized.lower() for token in ("uploaded academic material", "provided context", "source_indices")):
        errors.append("Question leaks retrieval or formatting artifacts")
    if not validate_co_rbt_alignment(task.co, task.rbt):
        errors.append(f"{task.co} is not allowed to use {task.rbt}")
    if task.marks >= 8 and len(normalized.split()) < 6:
        warnings.append("High-mark question may be too shallow")

    return QuestionValidation(ok=not errors, errors=errors, warnings=warnings)
