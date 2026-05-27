"""
Hierarchical Fallback Question Allocator.

Replaces the old strict-filter allocator with a production-grade
multi-stage pipeline that finds the BEST AVAILABLE match for each
blueprint slot instead of hard-rejecting when no exact match exists.

Allocation stages (in order):
  1. STRICT       — module + marks + CO + bloom (exact)
  2. BLOOM_RELAX  — module + marks + CO (any bloom)
  3. CO_RELAX     — module + marks (any CO, any bloom)
  4. MARKS_RELAX  — module + marks within tolerance [target-2, target+2]
  5. MODULE_ONLY  — any marks from same module
  6. QUESTION_SPLIT — split a higher-mark question from same module
  7. TEMPLATE     — compile a synthetic question from topic graph
"""

from __future__ import annotations

import enum
import logging
import random
from dataclasses import dataclass, field
from typing import Any

from .planning.blueprint_engine import QuestionTask

logger = logging.getLogger("app.academic.question_allocator")


# ---------------------------------------------------------------------------
# Derived Question & Matching Helpers
# ---------------------------------------------------------------------------


class DerivedQuestion:
    """A wrapper class for split and synthetic fallback questions that behaves
    like a database model, avoiding AttributeError when main.py sets attributes on it.
    """
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
        # Ensure standard attributes are present
        self.id = kwargs.get("id", -1)
        self.text = kwargs.get("text", "")
        self.marks = kwargs.get("marks", 5)
        self.course_outcome = kwargs.get("course_outcome", "CO1")
        self.bloom_level = kwargs.get("bloom_level", "L2")
        self.difficulty = kwargs.get("difficulty", "balanced")
        self.module_number = kwargs.get("module_number", 1)
        self.source_doc_id = kwargs.get("source_doc_id", None)
        self.tags = kwargs.get("tags", [])
        self.is_verified = kwargs.get("is_verified", False)
        self.source_documents = kwargs.get("source_documents", [])
        self.figure_image_paths = kwargs.get("figure_image_paths", [])

    def __getitem__(self, item):
        return getattr(self, item, None)

    def get(self, item, default=None):
        return getattr(self, item, default)


def _match_bloom(candidate_bloom: str | None, target_bloom: str | None) -> bool:
    if not candidate_bloom or not target_bloom:
        return False
    c_b = candidate_bloom.upper().strip()
    t_b = target_bloom.upper().strip()
    if c_b == t_b:
        return True
    if "/" in t_b:
        return c_b in [x.strip() for x in t_b.split("/")]
    if "/" in c_b:
        return t_b in [x.strip() for x in c_b.split("/")]
    return False


def _match_co(candidate_co: str | None, target_co: str | None) -> bool:
    if not candidate_co or not target_co:
        return False
    c_c = candidate_co.upper().strip()
    t_c = target_co.upper().strip()
    if c_c == t_c:
        return True
    if "/" in t_c:
        return c_c in [x.strip() for x in t_c.split("/")]
    if "/" in c_c:
        return t_c in [x.strip() for x in c_c.split("/")]
    return False

# ---------------------------------------------------------------------------
# Allocation level — tracks how close the match is
# ---------------------------------------------------------------------------


class AllocationLevel(enum.Enum):
    STRICT = "strict"
    BLOOM_RELAXED = "bloom_relaxed"
    CO_RELAXED = "co_relaxed"
    MARKS_RELAXED = "marks_relaxed"
    MODULE_ONLY = "module_only"
    QUESTION_SPLIT = "question_split"
    TEMPLATE_GENERATED = "template_generated"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AllocationResult:
    question: Any  # Question model instance or dict-like
    level: AllocationLevel
    confidence: float
    match_reason: str
    topic: str = ""
    source: str = "question_bank"
    split_from: Any = None  # original question if split


# ---------------------------------------------------------------------------
# Confidence calculation
# ---------------------------------------------------------------------------


_CONFIDENCE_BY_LEVEL: dict[AllocationLevel, float] = {
    AllocationLevel.STRICT: 1.0,
    AllocationLevel.BLOOM_RELAXED: 0.85,
    AllocationLevel.CO_RELAXED: 0.75,
    AllocationLevel.MARKS_RELAXED: 0.65,
    AllocationLevel.MODULE_ONLY: 0.50,
    AllocationLevel.QUESTION_SPLIT: 0.70,
    AllocationLevel.TEMPLATE_GENERATED: 0.40,
    AllocationLevel.UNAVAILABLE: 0.0,
}


def _get_slot_topic(slot: QuestionTask) -> str:
    return slot.topic if slot.topic else f"Module {slot.module}"


def _overall_confidence(
    slot: QuestionTask,
    candidate: Any,
    level: AllocationLevel,
) -> float:
    base = _CONFIDENCE_BY_LEVEL.get(level, 0.5)
    penalty = 0.0

    # Module alignment
    cand_mod = _get(candidate, "module_number")
    if cand_mod is not None and cand_mod != slot.module:
        penalty += 0.20

    # Marks mismatch penalty
    if hasattr(candidate, "marks") or isinstance(candidate, dict) or isinstance(candidate, DerivedQuestion):
        cand_marks = _get(candidate, "marks", 0)
        if cand_marks != slot.marks:
            diff = abs(cand_marks - slot.marks)
            penalty += 0.05 * diff

    # CO alignment
    cand_co = _get(candidate, "course_outcome", "")
    if cand_co and not _match_co(cand_co, slot.co):
        penalty += 0.10

    # Bloom alignment
    cand_bloom = _get(candidate, "bloom_level", "")
    if cand_bloom and not _match_bloom(cand_bloom, slot.rbt):
        penalty += 0.10

    # Topic alignment (bonus or penalty)
    slot_topic = getattr(slot, "topic", "")
    cand_topic = _get(candidate, "topic", "")
    if slot_topic and cand_topic:
        slot_t_clean = slot_topic.lower().strip()
        cand_t_clean = cand_topic.lower().strip()
        if slot_t_clean == cand_t_clean:
            penalty -= 0.05  # bonus
        elif slot_t_clean in cand_t_clean or cand_t_clean in slot_t_clean:
            penalty -= 0.02  # small bonus
        else:
            penalty += 0.05  # small penalty

    # Guarantee split and template confidence are reasonable
    if level == AllocationLevel.QUESTION_SPLIT:
        base = 0.75
    elif level == AllocationLevel.TEMPLATE_GENERATED:
        base = 0.60

    return max(0.2, min(1.0, base - penalty))


# ---------------------------------------------------------------------------
# Helper: safely read attributes from Question objects or dicts
# ---------------------------------------------------------------------------


def _get(obj: Any, key: str, default: Any = None) -> Any:
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


# ---------------------------------------------------------------------------
# Stage 2 — relaxed bloom
# ---------------------------------------------------------------------------

def _find_bloom_relaxed(
    candidates: list[Any],
    slot: QuestionTask,
    used_ids: set[int],
) -> Any | None:
    for c in candidates:
        cid = _get(c, "id")
        if cid in used_ids:
            continue
        mod = _get(c, "module_number")
        marks = _get(c, "marks")
        co = _get(c, "course_outcome", "")
        if mod == slot.module and marks == slot.marks and _match_co(co, slot.co):
            return c
    return None


# ---------------------------------------------------------------------------
# Stage 3 — relaxed CO
# ---------------------------------------------------------------------------

def _find_co_relaxed(
    candidates: list[Any],
    slot: QuestionTask,
    used_ids: set[int],
) -> Any | None:
    for c in candidates:
        cid = _get(c, "id")
        if cid in used_ids:
            continue
        mod = _get(c, "module_number")
        marks = _get(c, "marks")
        if mod == slot.module and marks == slot.marks:
            return c
    return None


# ---------------------------------------------------------------------------
# Stage 4 — marks relaxed (tolerance window)
# ---------------------------------------------------------------------------

def _find_marks_relaxed(
    candidates: list[Any],
    slot: QuestionTask,
    used_ids: set[int],
    tolerance: int = 1,
) -> Any | None:
    # First try to match module, CO, and marks in range
    for c in candidates:
        cid = _get(c, "id")
        if cid in used_ids:
            continue
        mod = _get(c, "module_number")
        marks = _get(c, "marks")
        co = _get(c, "course_outcome", "")
        if mod == slot.module and _match_co(co, slot.co) and abs(marks - slot.marks) <= tolerance:
            return c
    # Fallback: match module and marks in range
    for c in candidates:
        cid = _get(c, "id")
        if cid in used_ids:
            continue
        mod = _get(c, "module_number")
        marks = _get(c, "marks")
        if mod == slot.module and abs(marks - slot.marks) <= tolerance:
            return c
    return None


# ---------------------------------------------------------------------------
# Stage 5 — module only
# ---------------------------------------------------------------------------

def _find_module_only(
    candidates: list[Any],
    slot: QuestionTask,
    used_ids: set[int],
) -> Any | None:
    # First try to match module and CO
    for c in candidates:
        cid = _get(c, "id")
        if cid in used_ids:
            continue
        mod = _get(c, "module_number")
        co = _get(c, "course_outcome", "")
        if mod == slot.module and _match_co(co, slot.co):
            return c
    # Fallback to module only
    for c in candidates:
        cid = _get(c, "id")
        if cid in used_ids:
            continue
        mod = _get(c, "module_number")
        if mod == slot.module:
            return c
    return None


# ---------------------------------------------------------------------------
# Stage 6 — question split
# ---------------------------------------------------------------------------

def _split_high_mark_question(
    source: Any,
    target_marks: int,
) -> tuple[str, str] | None:
    """Split a high-mark question into two sub-questions.

    Returns (part_a, part_b) or None if unsuitable.
    """
    text = _get(source, "text", "")
    if not text or len(text) < 40:
        return None
    marks = _get(source, "marks", 0)
    if marks < target_marks * 2:
        return None

    # Try splitting on common delimiters
    delimiters = [
        ". ",
        ".Explain",
        ". Describe",
        ". Discuss",
        ". Analyse",
        ". Analyze",
        ". Compare",
        ". Differentiate",
        ". Evaluate",
        ". Design",
        ". Develop",
        ".Prove",
        ". Show",
    ]
    best_split = None
    best_midpoint_dist = float("inf")
    midpoint = len(text) // 2

    for delim in delimiters:
        pos = text.find(delim, len(text) // 3, 2 * len(text) // 3)
        if 0 < pos < len(text) - 10:
            dist = abs(pos - midpoint)
            if dist < best_midpoint_dist:
                best_midpoint_dist = dist
                best_split = pos + len(delim)

    if best_split is not None:
        part_a = text[:best_split].strip().rstrip(".") + "."
        part_b = text[best_split:].strip().lstrip("., ")
        if len(part_a) > 15 and len(part_b) > 15:
            return (part_a, part_b)

    # Fallback: split into two sentences
    sentences = [s.strip() for s in text.replace(". ", ".|").split("|") if len(s.strip()) > 15]
    if len(sentences) >= 2:
        half = max(1, len(sentences) // 2)
        part_a = ". ".join(sentences[:half]) + "."
        part_b = ". ".join(sentences[half:])
        if not part_b.endswith("."):
            part_b += "."
        return (part_a, part_b)

    return None


def _find_split_candidate(
    candidates: list[Any],
    slot: QuestionTask,
    used_ids: set[int],
) -> tuple[Any, tuple[str, str]] | None:
    """Find a higher-mark question to split into two slot-sized parts."""
    # First try to match CO
    for c in candidates:
        cid = _get(c, "id")
        marks = _get(c, "marks")
        mod = _get(c, "module_number")
        co = _get(c, "course_outcome", "")
        if cid in used_ids:
            continue
        if mod == slot.module and _match_co(co, slot.co) and marks >= slot.marks * 1.5:
            parts = _split_high_mark_question(c, slot.marks)
            if parts:
                return (c, parts)
    # Fallback to module only
    for c in candidates:
        cid = _get(c, "id")
        marks = _get(c, "marks")
        mod = _get(c, "module_number")
        if cid in used_ids:
            continue
        if mod == slot.module and marks >= slot.marks * 1.5:
            parts = _split_high_mark_question(c, slot.marks)
            if parts:
                return (c, parts)
    return None


# ---------------------------------------------------------------------------
# Stage 7 — template generation fallback
# ---------------------------------------------------------------------------

def _generate_fallback(
    slot: QuestionTask,
    db: Any = None,
    subject_id: int | None = None,
) -> Any | None:
    """Generate a synthetic question as last resort."""
    try:
        from .templates import compile_question
        from ..models import Question

        topic = slot.topic if slot.topic else f"Module {slot.module} Core Concepts"
        keywords = [topic]
        if hasattr(slot, "keywords") and slot.keywords:
            keywords = slot.keywords

        q_text = compile_question(
            topic=topic,
            bloom_level=slot.rbt or "L2",
            keywords=keywords,
            marks=slot.marks,
            is_image_question=False,
        )

        if db is not None and subject_id is not None:
            from ..models import User
            admin = db.query(User).filter(User.role == "admin").first()
            teacher_id = admin.id if admin else 1

            q_row = Question(
                subject_id=subject_id,
                teacher_id=teacher_id,
                text=q_text,
                marks=slot.marks,
                course_outcome=slot.co,
                bloom_level=slot.rbt,
                difficulty="balanced",
                module_number=slot.module,
                tags=["system-generated", "fallback"],
                is_verified=False,
            )
            db.add(q_row)
            db.flush()
            return q_row

        # Return DerivedQuestion if no db
        return DerivedQuestion(
            id=-1,
            text=q_text,
            marks=slot.marks,
            course_outcome=slot.co,
            bloom_level=slot.rbt,
            difficulty="balanced",
            module_number=slot.module,
            tags=["system-generated", "fallback"],
            is_verified=False,
            source_documents=["Syllabus / Topic Graph"],
            confidence=0.6,
            topic=topic,
        )
    except Exception as e:
        logger.warning("Template generation failed for slot %s: %s", slot.label, e)
        return None


# ---------------------------------------------------------------------------
# Master allocation function
# ---------------------------------------------------------------------------


def allocate_for_slot(
    slot: QuestionTask,
    pool: list[Any],
    used_ids: set[int],
    db: Any = None,
    subject_id: int | None = None,
    split_cache: dict[int, tuple[Any, str]] | None = None,
    require_image: bool = False,
) -> AllocationResult:
    """Run the hierarchical fallback pipeline for a single blueprint slot.

    Args:
        slot: The blueprint slot (QuestionTask).
        pool: All available questions from the bank.
        used_ids: Set of already-allocated question IDs (mutated in-place).
        db: Optional DB session for template generation.
        subject_id: Required if db is given.
        split_cache: Optional cache of split question parts to reuse for choices.
        require_image: If True, prioritizes selecting an image question from the pool.

    Returns:
        AllocationResult with the best found match.
    """
    if require_image:
        image_pool = [c for c in pool if _get(c, "image_path") is not None]
        if image_pool:
            res = allocate_for_slot(
                slot, image_pool, used_ids, db=None, subject_id=None, split_cache=split_cache, require_image=False
            )
            if res and res.level not in (AllocationLevel.TEMPLATE_GENERATED, AllocationLevel.UNAVAILABLE):
                actual_qid = _get(res.question, "id")
                if actual_qid > 0:
                    used_ids.add(actual_qid)
                return res

    marks = slot.marks
    module = slot.module
    co = slot.co.upper()
    bloom = slot.rbt.upper()

    # ----- Stage 0: REUSE CACHED SPLIT PART -----
    if split_cache and slot.question_number in split_cache:
        source, part_text = split_cache[slot.question_number]
        source_id = _get(source, "id")
        sub_q = DerivedQuestion(
            id=-source_id - 1000000,
            text=part_text,
            marks=slot.marks,
            course_outcome=_get(source, "course_outcome", slot.co),
            bloom_level=_get(source, "bloom_level", slot.rbt),
            difficulty=_get(source, "difficulty", "balanced"),
            module_number=slot.module,
            tags=_get(source, "tags", []) + ["auto-split", f"part-{slot.subpart or 'b'}"],
            is_verified=_get(source, "is_verified", False),
            source_documents=_get(source, "source_documents", []),
            topic=_get(source, "topic", _get_slot_topic(slot)),
        )
        logger.info("QUESTION_SPLIT CACHED REUSE: Allocated cached part for slot %s (q=%d)", slot.label, source_id)
        return AllocationResult(
            question=sub_q,
            level=AllocationLevel.QUESTION_SPLIT,
            confidence=_overall_confidence(slot, source, AllocationLevel.QUESTION_SPLIT),
            match_reason=f"Auto-split part ({slot.subpart or 'b'}) from {_get(source, 'marks', 0)}M question",
            topic=_get(source, "topic", _get_slot_topic(slot)),
            source="auto_split",
            split_from=source,
        )

    # ----- Stage 1: STRICT MATCH -----
    strict = [
        c for c in pool
        if _get(c, "module_number") == module
        and _get(c, "marks") == marks
        and _match_co(_get(c, "course_outcome", ""), co)
        and _match_bloom(_get(c, "bloom_level", ""), bloom)
        and _get(c, "id") not in used_ids
    ]
    if strict:
        q = random.choice(strict)
        used_ids.add(_get(q, "id"))
        logger.info("STRICT match for slot %s (q=%d)", slot.label, _get(q, "id"))
        return AllocationResult(
            question=q,
            level=AllocationLevel.STRICT,
            confidence=_overall_confidence(slot, q, AllocationLevel.STRICT),
            match_reason=f"Exact match: M{module} {marks}M {co} {bloom}",
            topic=_get(q, "topic", _get_slot_topic(slot)),
        )

    # ----- Stage 2: RELAX BLOOM -----
    q = _find_bloom_relaxed(pool, slot, used_ids)
    if q:
        used_ids.add(_get(q, "id"))
        logger.info("BLOOM_RELAXED match for slot %s (q=%d)", slot.label, _get(q, "id"))
        return AllocationResult(
            question=q,
            level=AllocationLevel.BLOOM_RELAXED,
            confidence=_overall_confidence(slot, q, AllocationLevel.BLOOM_RELAXED),
            match_reason=f"Relaxed bloom: M{module} {marks}M {co} (bloom: {_get(q, 'bloom_level', '?')})",
            topic=_get(q, "topic", _get_slot_topic(slot)),
        )

    # ----- Stage 3: RELAX CO -----
    q = _find_co_relaxed(pool, slot, used_ids)
    if q:
        used_ids.add(_get(q, "id"))
        logger.info("CO_RELAXED match for slot %s (q=%d)", slot.label, _get(q, "id"))
        return AllocationResult(
            question=q,
            level=AllocationLevel.CO_RELAXED,
            confidence=_overall_confidence(slot, q, AllocationLevel.CO_RELAXED),
            match_reason=f"Relaxed CO: M{module} {marks}M (co: {_get(q, 'course_outcome', '?')}, bloom: {_get(q, 'bloom_level', '?')})",
            topic=_get(q, "topic", _get_slot_topic(slot)),
        )

    # ----- Stage 4: RELAX MARKS (tolerance) -----
    q = _find_marks_relaxed(pool, slot, used_ids)
    if q:
        used_ids.add(_get(q, "id"))
        actual = _get(q, "marks", 0)
        logger.info("MARKS_RELAXED match for slot %s (q=%d, %dM)", slot.label, _get(q, "id"), actual)
        return AllocationResult(
            question=q,
            level=AllocationLevel.MARKS_RELAXED,
            confidence=_overall_confidence(slot, q, AllocationLevel.MARKS_RELAXED),
            match_reason=f"Relaxed marks: M{module} {actual}M (target: {marks}M)",
            topic=_get(q, "topic", _get_slot_topic(slot)),
        )

    # ----- Stage 5: MODULE ONLY -----
    q = _find_module_only(pool, slot, used_ids)
    if q:
        used_ids.add(_get(q, "id"))
        actual = _get(q, "marks", 0)
        logger.info("MODULE_ONLY match for slot %s (q=%d, %dM)", slot.label, _get(q, "id"), actual)
        return AllocationResult(
            question=q,
            level=AllocationLevel.MODULE_ONLY,
            confidence=_overall_confidence(slot, q, AllocationLevel.MODULE_ONLY),
            match_reason=f"Module-only: M{module} {actual}M (target: {marks}M)",
            topic=_get(q, "topic", _get_slot_topic(slot)),
        )

    # ----- Stage 6: QUESTION SPLIT -----
    result = _find_split_candidate(pool, slot, used_ids)
    if result:
        source, parts = result
        part_a, part_b = parts
        source_id = _get(source, "id")
        used_ids.add(source_id)

        # Store the second part in split_cache!
        if split_cache is not None:
            split_cache[slot.question_number] = (source, part_b)

        # Create a DerivedQuestion sub-question for this slot
        sub_q = DerivedQuestion(
            id=-source_id,
            text=part_a,
            marks=slot.marks,
            course_outcome=_get(source, "course_outcome", slot.co),
            bloom_level=_get(source, "bloom_level", slot.rbt),
            difficulty=_get(source, "difficulty", "balanced"),
            module_number=slot.module,
            tags=_get(source, "tags", []) + ["auto-split", "part-a"],
            is_verified=_get(source, "is_verified", False),
            source_documents=_get(source, "source_documents", []),
            topic=_get(source, "topic", _get_slot_topic(slot)),
        )
        logger.info("QUESTION_SPLIT for slot %s from q=%d", slot.label, source_id)
        return AllocationResult(
            question=sub_q,
            level=AllocationLevel.QUESTION_SPLIT,
            confidence=_overall_confidence(slot, source, AllocationLevel.QUESTION_SPLIT),
            match_reason=f"Auto-split from {_get(source, 'marks', 0)}M question",
            topic=_get(source, "topic", _get_slot_topic(slot)),
            source="auto_split",
            split_from=source,
        )

    # ----- Stage 7: TEMPLATE GENERATION -----
    q = _generate_fallback(slot, db=db, subject_id=subject_id)
    if q:
        qid = _get(q, "id", -1)
        if qid > 0:
            used_ids.add(qid)
        logger.info("TEMPLATE_GENERATED for slot %s", slot.label)
        return AllocationResult(
            question=q,
            level=AllocationLevel.TEMPLATE_GENERATED,
            confidence=_overall_confidence(slot, q, AllocationLevel.TEMPLATE_GENERATED),
            match_reason="System-generated fallback question",
            topic=_get_slot_topic(slot),
            source="template_generated",
        )

    # ----- Stage 8: ABSOLUTE FALLBACK -----
    q_text = f"Explain the key concepts and practical applications of {_get_slot_topic(slot)}."
    sub_q = DerivedQuestion(
        id=-999,
        text=q_text,
        marks=slot.marks,
        course_outcome=slot.co,
        bloom_level=slot.rbt,
        difficulty="balanced",
        module_number=slot.module,
        tags=["system-generated", "absolute-fallback"],
        is_verified=False,
        source_documents=["Syllabus / Topic Graph"],
        confidence=0.35,
        topic=_get_slot_topic(slot),
    )
    logger.info("ABSOLUTE_FALLBACK for slot %s", slot.label)
    return AllocationResult(
        question=sub_q,
        level=AllocationLevel.TEMPLATE_GENERATED,
        confidence=0.35,
        match_reason="Absolute system-generated fallback question",
        topic=_get_slot_topic(slot),
        source="template_generated",
    )


# ---------------------------------------------------------------------------
# Batch allocation: allocate for an entire blueprint
# ---------------------------------------------------------------------------


def allocate_blueprint(
    blueprint: list[QuestionTask],
    pool: list[Any],
    db: Any = None,
    subject_id: int | None = None,
    module_image_map: dict[int, bool] | None = None,
) -> list[AllocationResult]:
    """Allocate questions for every slot in a blueprint.

    First pass: strict matches for all slots.
    Second pass: relaxed matches for remaining unfilled slots.
    This ensures fairness across slots.
    """
    used_ids: set[int] = set()
    results: list[AllocationResult | None] = [None] * len(blueprint)
    split_cache: dict[int, tuple[Any, str]] = {}
    
    image_modules = {mod for mod, include in (module_image_map or {}).items() if include}
    allocated_image_for_module: set[int] = set()

    # Pass 1: STRICT for all slots (fairness)
    for i, slot in enumerate(blueprint):
        # If this module requires an image and we haven't allocated one yet, try strict image questions first!
        if slot.module in image_modules and slot.module not in allocated_image_for_module:
            strict_image = [
                c for c in pool
                if _get(c, "module_number") == slot.module
                and _get(c, "marks") == slot.marks
                and _match_co(_get(c, "course_outcome", ""), slot.co)
                and _match_bloom(_get(c, "bloom_level", ""), slot.rbt)
                and _get(c, "id") not in used_ids
                and _get(c, "image_path") is not None
            ]
            if strict_image:
                q = random.choice(strict_image)
                used_ids.add(_get(q, "id"))
                allocated_image_for_module.add(slot.module)
                results[i] = AllocationResult(
                    question=q,
                    level=AllocationLevel.STRICT,
                    confidence=_overall_confidence(slot, q, AllocationLevel.STRICT),
                    match_reason=f"Exact match with image: M{slot.module} {slot.marks}M {slot.co} {slot.rbt}",
                    topic=_get(q, "topic", _get_slot_topic(slot)),
                )
                continue

        strict = [
            c for c in pool
            if _get(c, "module_number") == slot.module
            and _get(c, "marks") == slot.marks
            and _match_co(_get(c, "course_outcome", ""), slot.co)
            and _match_bloom(_get(c, "bloom_level", ""), slot.rbt)
            and _get(c, "id") not in used_ids
        ]
        if strict:
            q = random.choice(strict)
            used_ids.add(_get(q, "id"))
            if _get(q, "image_path") is not None:
                allocated_image_for_module.add(slot.module)
            results[i] = AllocationResult(
                question=q,
                level=AllocationLevel.STRICT,
                confidence=_overall_confidence(slot, q, AllocationLevel.STRICT),
                match_reason=f"Exact match: M{slot.module} {slot.marks}M {slot.co} {slot.rbt}",
                topic=_get(q, "topic", _get_slot_topic(slot)),
            )

    # Pass 2: Relaxed fallback for remaining slots
    for i, slot in enumerate(blueprint):
        if results[i] is not None:
            continue
            
        req_img = (slot.module in image_modules and slot.module not in allocated_image_for_module)
        res = allocate_for_slot(
            slot, pool, used_ids, db=db, subject_id=subject_id, split_cache=split_cache, require_image=req_img
        )
        if res and res.question and _get(res.question, "image_path") is not None:
            allocated_image_for_module.add(slot.module)
        results[i] = res

    return results  # type: ignore[return-value]

