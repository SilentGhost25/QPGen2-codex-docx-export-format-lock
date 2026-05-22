"""
Academic validation engine for generated questions.

Validates:
- Syllabus compliance (topic must exist in syllabus)
- Bloom level compliance
- CO alignment
- Topic presence in retrieved context (anti-hallucination)
- VTU phrasing patterns
- Marks distribution
- Semantic deduplication
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .embeddings import cosine_similarity, generate_embedding
from .retrieval import RetrievedContext

logger = logging.getLogger("app.academic.validation")


# ---------------------------------------------------------------------------
# VTU Academic Style
# ---------------------------------------------------------------------------

VTU_VERBS: dict[str, tuple[str, ...]] = {
    "L1": ("define", "list", "state", "name", "identify", "recall", "mention"),
    "L2": ("explain", "describe", "discuss", "summarize", "outline", "differentiate"),
    "L3": ("solve", "calculate", "apply", "demonstrate", "implement", "compute", "write"),
    "L4": ("analyze", "compare", "distinguish", "examine", "contrast", "classify"),
    "L5": ("evaluate", "justify", "critique", "assess", "argue", "judge"),
    "L6": ("design", "develop", "construct", "create", "formulate", "propose"),
}

# Flatten for quick lookup
_ALL_VTU_VERBS = set()
for _verbs in VTU_VERBS.values():
    _ALL_VTU_VERBS.update(_verbs)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    """A single validation issue."""
    category: str  # syllabus, bloom, co, topic, phrasing, marks, duplicate
    severity: str  # error, warning, info
    message: str
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Result of validating a generated question."""
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    confidence: float = 1.0

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]


# ---------------------------------------------------------------------------
# Individual validators
# ---------------------------------------------------------------------------

def validate_topic_in_context(
    question_text: str,
    retrieved_contexts: list[RetrievedContext],
    threshold: float = 0.3,
) -> ValidationIssue | None:
    """
    CRITICAL: Ensure the question topic exists in retrieved context.
    This is the primary anti-hallucination check.
    """
    if not retrieved_contexts:
        return ValidationIssue(
            category="topic",
            severity="error",
            message="No retrieved context available — question may be hallucinated",
            suggestion="Upload relevant notes/materials before generating questions",
        )

    q_embedding = generate_embedding(question_text)
    if not q_embedding:
        # Fallback to text matching
        q_lower = question_text.lower()
        for ctx in retrieved_contexts:
            # Check if significant words overlap
            ctx_words = set(re.findall(r"\w{4,}", ctx.text.lower()))
            q_words = set(re.findall(r"\w{4,}", q_lower))
            overlap = len(q_words & ctx_words)
            if overlap >= 3 or (q_words and overlap / len(q_words) >= 0.3):
                return None
        return ValidationIssue(
            category="topic",
            severity="error",
            message="Question topic not found in any retrieved context",
            suggestion="This question may contain hallucinated content",
        )

    # Check semantic similarity with retrieved chunks
    best_score = 0.0
    for ctx in retrieved_contexts:
        ctx_embedding = generate_embedding(ctx.text)
        if ctx_embedding:
            score = cosine_similarity(q_embedding, ctx_embedding)
            best_score = max(best_score, score)

    if best_score < threshold:
        return ValidationIssue(
            category="topic",
            severity="error",
            message=f"Question has low relevance to retrieved context (best match: {best_score:.2f})",
            suggestion="Question may be outside the scope of uploaded materials",
        )
    return None


def validate_bloom_level(
    question_text: str,
    declared_bloom: str,
) -> ValidationIssue | None:
    """Check if the question text matches its declared Bloom level."""
    from .policies import has_rbt_action_verb, RBT_VERBS
    
    clean_rbt = declared_bloom.strip().upper()
    expected_verbs = RBT_VERBS.get(clean_rbt, [])

    if not expected_verbs:
        return ValidationIssue(
            category="bloom",
            severity="warning",
            message=f"Unknown Bloom level: {declared_bloom}",
            suggestion="Use L1-L6",
        )

    if not has_rbt_action_verb(question_text, clean_rbt):
        # Scan if another level matches
        detected_level = None
        for level in RBT_VERBS:
            if has_rbt_action_verb(question_text, level):
                detected_level = level
                break

        if detected_level and detected_level != clean_rbt:
            return ValidationIssue(
                category="bloom",
                severity="warning",
                message=f"Question aligns better with {detected_level} but declared as {clean_rbt}",
                suggestion=f"To comply with university guidelines, please rephrase using a valid {clean_rbt} verb: {', '.join(expected_verbs[:3])}",
            )
        else:
            return ValidationIssue(
                category="bloom",
                severity="info",
                message=f"Question does not start with standard {clean_rbt} action verbs",
                suggestion=f"Consider using one of these verbs: {', '.join(expected_verbs[:3])}",
            )
    return None


def validate_co_alignment(
    question_text: str,
    declared_co: str,
    bloom_level: str,
    co_definitions: dict[str, str] | None = None,
) -> ValidationIssue | None:
    """Check if CO assignment is reasonable."""
    if not declared_co or not declared_co.startswith("CO"):
        return ValidationIssue(
            category="co",
            severity="warning",
            message=f"Invalid CO format: {declared_co}",
            suggestion="Use CO1-CO6",
        )

    # Basic bloom-CO consistency check using global policy
    from .policies import validate_co_rbt_alignment, get_allowed_rbt
    if not validate_co_rbt_alignment(declared_co, bloom_level):
        allowed = get_allowed_rbt(declared_co)
        return ValidationIssue(
            category="co",
            severity="error",
            message=f"Strict academic policy violation: {declared_co} does not support Bloom level {bloom_level} (allowed: {', '.join(allowed)})",
            suggestion=f"Target one of the allowed Bloom levels for {declared_co}: {', '.join(allowed)}",
        )

    # Basic bloom-CO consistency check (informational fallback)
    bloom_to_typical_co = {
        "L1": {"CO1", "CO2"},
        "L2": {"CO1", "CO2", "CO3"},
        "L3": {"CO2", "CO3", "CO4"},
        "L4": {"CO3", "CO4", "CO5"},
        "L5": {"CO4", "CO5"},
        "L6": {"CO4", "CO5", "CO6"},
    }
    typical_cos = bloom_to_typical_co.get(bloom_level, set())
    if typical_cos and declared_co not in typical_cos:
        return ValidationIssue(
            category="co",
            severity="info",
            message=f"{declared_co} is unusual for {bloom_level} questions (typical: {', '.join(sorted(typical_cos))})",
        )
    return None


def validate_vtu_phrasing(question_text: str) -> list[ValidationIssue]:
    """Check if question follows VTU academic phrasing patterns."""
    issues: list[ValidationIssue] = []
    lowered = question_text.lower().strip()

    # Should start with an action verb or question word
    starts_with_verb = any(lowered.startswith(verb) for verb in _ALL_VTU_VERBS)
    starts_with_question_word = any(
        lowered.startswith(w) for w in ("what", "how", "why", "when", "where", "which", "who")
    )

    if not starts_with_verb and not starts_with_question_word:
        issues.append(ValidationIssue(
            category="phrasing",
            severity="info",
            message="Question doesn't start with a standard VTU action verb",
            suggestion="Consider starting with: Define, Explain, Describe, Solve, Analyze, Design, etc.",
        ))

    # Should have reasonable length
    word_count = len(question_text.split())
    if word_count < 5:
        issues.append(ValidationIssue(
            category="phrasing",
            severity="warning",
            message="Question is too short for academic use",
            suggestion="Expand with more context or specificity",
        ))
    elif word_count > 200:
        issues.append(ValidationIssue(
            category="phrasing",
            severity="info",
            message="Question is unusually long",
            suggestion="Consider splitting into sub-parts or simplifying",
        ))

    return issues


def validate_marks_appropriateness(
    marks: int,
    bloom_level: str,
    question_text: str,
) -> ValidationIssue | None:
    """Check if marks allocation is reasonable for the question type."""
    word_count = len(question_text.split())

    if bloom_level in {"L1", "L2"} and marks > 10:
        return ValidationIssue(
            category="marks",
            severity="info",
            message=f"{marks} marks is high for an {bloom_level} question",
            suggestion="L1/L2 questions typically carry 2-10 marks",
        )

    if marks >= 15 and word_count < 15:
        return ValidationIssue(
            category="marks",
            severity="warning",
            message="High marks but very short question text",
            suggestion="A 15+ mark question should have more detail or sub-parts",
        )
    return None


def validate_duplicate(
    question_text: str,
    existing_questions: list[str],
    threshold: float = 0.85,
) -> ValidationIssue | None:
    """Check for semantic duplication against existing questions."""
    if not existing_questions:
        return None

    # 1. High-speed text-based overlap fallback check
    q_words = set(re.findall(r"\w{4,}", question_text.lower()))
    for existing in existing_questions:
        exist_words = set(re.findall(r"\w{4,}", existing.lower()))
        if q_words and exist_words:
            intersection = len(q_words & exist_words)
            union = len(q_words | exist_words)
            jaccard = intersection / union
            if jaccard >= 0.70:  # Strong token level overlap
                return ValidationIssue(
                    category="duplicate",
                    severity="error",
                    message=f"Question has high keyword overlap with an existing question (Jaccard index: {jaccard:.2f})",
                    suggestion="Rephrase significantly to target a different concept",
                )

    # 2. Semantic vector-based duplication check
    q_embedding = generate_embedding(question_text)
    if not q_embedding:
        return None

    for existing in existing_questions:
        existing_embedding = generate_embedding(existing)
        if existing_embedding:
            similarity = cosine_similarity(q_embedding, existing_embedding)
            if similarity >= threshold:
                return ValidationIssue(
                    category="duplicate",
                    severity="error",
                    message=f"Question is semantically identical or highly similar to an existing question (similarity: {similarity:.2f})",
                    suggestion="Select a different topic or reframe the prompt context",
                )
    return None


def validate_syllabus_compliance(
    question_text: str,
    topic_name: str | None,
    module_number: int | None,
    syllabus_topics: list[str] | None,
) -> ValidationIssue | None:
    """Check if the question aligns with the syllabus."""
    if not syllabus_topics:
        return None  # Can't validate without syllabus

    if topic_name:
        topic_lower = topic_name.lower()
        for syllabus_topic in syllabus_topics:
            if topic_lower in syllabus_topic.lower() or syllabus_topic.lower() in topic_lower:
                return None  # Match found

    # Check question text against syllabus topics
    q_lower = question_text.lower()
    for syllabus_topic in syllabus_topics:
        topic_words = set(re.findall(r"\w{4,}", syllabus_topic.lower()))
        q_words = set(re.findall(r"\w{4,}", q_lower))
        if topic_words and len(topic_words & q_words) >= 2:
            return None

    return ValidationIssue(
        category="syllabus",
        severity="warning",
        message="Question topic may not align with the subject syllabus",
        suggestion="Verify that this topic is covered in the syllabus",
    )


# ---------------------------------------------------------------------------
# Complete validation pipeline
# ---------------------------------------------------------------------------

def validate_question(
    question_text: str,
    marks: int,
    bloom_level: str,
    co_mapping: str,
    *,
    retrieved_contexts: list[RetrievedContext] | None = None,
    existing_questions: list[str] | None = None,
    syllabus_topics: list[str] | None = None,
    co_definitions: dict[str, str] | None = None,
    topic_name: str | None = None,
    module_number: int | None = None,
) -> ValidationResult:
    """
    Run the complete validation pipeline on a generated question.

    Returns ValidationResult with is_valid=False if any errors are found.
    """
    issues: list[ValidationIssue] = []

    # 1. Topic in context (CRITICAL anti-hallucination)
    if retrieved_contexts is not None:
        issue = validate_topic_in_context(question_text, retrieved_contexts)
        if issue:
            issues.append(issue)

    # 2. Bloom level compliance
    issue = validate_bloom_level(question_text, bloom_level)
    if issue:
        issues.append(issue)

    # 3. CO alignment
    issue = validate_co_alignment(question_text, co_mapping, bloom_level, co_definitions)
    if issue:
        issues.append(issue)

    # 4. VTU phrasing
    phrasing_issues = validate_vtu_phrasing(question_text)
    issues.extend(phrasing_issues)

    # 5. Marks appropriateness
    issue = validate_marks_appropriateness(marks, bloom_level, question_text)
    if issue:
        issues.append(issue)

    # 6. Duplicate check
    if existing_questions:
        issue = validate_duplicate(question_text, existing_questions)
        if issue:
            issues.append(issue)

    # 7. Syllabus compliance
    if syllabus_topics:
        issue = validate_syllabus_compliance(question_text, topic_name, module_number, syllabus_topics)
        if issue:
            issues.append(issue)

    # Determine validity
    has_errors = any(i.severity == "error" for i in issues)
    warning_count = sum(1 for i in issues if i.severity == "warning")
    confidence = 1.0 - (0.3 * len([i for i in issues if i.severity == "error"])) - (0.1 * warning_count)
    confidence = max(0.0, min(1.0, confidence))

    return ValidationResult(
        is_valid=not has_errors,
        issues=issues,
        confidence=round(confidence, 3),
    )
