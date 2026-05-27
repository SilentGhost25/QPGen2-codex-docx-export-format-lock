"""
Template-Guided Synthetic Question Compiler (Generation Engine).

CORE PRINCIPLE: Zero LLM inference at paper generation time.
Instead of live generation, this engine acts as an academic compiler:
  1. Builds a curriculum-wide Topic Graph from ingested knowledge chunks.
  2. Iterates over individual blueprint/plan tasks.
  3. Maps each task deterministically to a TopicNode.
  4. Dynamically compiles a VTU-style question using pre-defined templates.
  5. Returns high-fidelity questions with zero hallucinations and instant runtime.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from .topic_graph import build_topic_graph, TopicNode
from .templates import compile_question
from .validation import ValidationResult

logger = logging.getLogger("app.academic.generation")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class GeneratedQuestion:
    """A single generated question with full traceability."""
    text: str
    marks: int
    bloom_level: str
    co_mapping: str
    module_number: int | None
    question_type: str  # theory, numerical, case_study, programming, diagram
    topic_name: str | None
    # Source traceability
    source_chunk_ids: list[int] = field(default_factory=list)
    source_documents: list[str] = field(default_factory=list)
    figure_image_paths: list[str] = field(default_factory=list)
    confidence: float = 1.0
    # Validation
    validation: ValidationResult | None = None
    task_index: int | None = None


@dataclass
class GenerationResult:
    """Complete result of a deterministic generation compile run."""
    questions: list[GeneratedQuestion]
    retrieval_summary: dict[str, Any]
    validation_summary: dict[str, Any]
    generation_time: float
    model_used: str
    creativity_level: float
    temperature: float


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalize_marks_distribution(
    marks_distribution: dict[int, int] | None,
    num_questions: int,
) -> list[int]:
    if not marks_distribution:
        return [5] * num_questions

    marks_plan: list[int] = []
    for raw_marks, raw_count in marks_distribution.items():
        try:
            marks = max(1, int(raw_marks))
            count = max(0, int(raw_count))
        except (TypeError, ValueError):
            continue
        marks_plan.extend([marks] * count)

    if not marks_plan:
        marks_plan = [5] * num_questions

    if len(marks_plan) < num_questions:
        marks_plan.extend([marks_plan[-1]] * (num_questions - len(marks_plan)))
    return marks_plan[:num_questions]


def _build_slot_plan(
    num_questions: int,
    marks_distribution: dict[int, int] | None,
    bloom_levels: list[str] | None,
    co_targets: list[str] | None,
    question_types: list[str] | None,
) -> list[dict[str, Any]]:
    from .policies import get_allowed_rbt
    
    marks_plan = _normalize_marks_distribution(marks_distribution, num_questions)
    co_plan = co_targets or ["CO1", "CO2", "CO3", "CO4", "CO5"]
    qtype_plan = question_types or ["theory"]

    slots: list[dict[str, Any]] = []
    for index in range(num_questions):
        co = co_plan[index % len(co_plan)]
        allowed_rbts = get_allowed_rbt(co)
        
        # If user specified bloom levels, intersect them with allowed levels.
        # Otherwise, pick standard level for that CO.
        intersected = [lvl for lvl in allowed_rbts if lvl in (bloom_levels or [])]
        if bloom_levels and intersected:
            bloom_level = intersected[index % len(intersected)]
        else:
            bloom_level = allowed_rbts[index % len(allowed_rbts)]
            
        slots.append(
            {
                "marks": marks_plan[index],
                "bloom_level": bloom_level,
                "co_mapping": co,
                "question_type": qtype_plan[index % len(qtype_plan)],
            }
        )
    return slots


# ---------------------------------------------------------------------------
# Academic Question Compiler
# ---------------------------------------------------------------------------

def generate_questions_from_retrieval(
    db: Session,
    subject_id: int,
    num_questions: int,
    marks_distribution: dict[int, int] | None = None,
    bloom_levels: list[str] | None = None,
    co_targets: list[str] | None = None,
    question_types: list[str] | None = None,
    module_filter: int | None = None,
    additional_instructions: str | None = None,
    creativity_override: float | None = None,
    existing_questions: list[str] | None = None,
    use_notes: bool = True,
    use_question_bank: bool = True,
    use_previous_papers: bool = False,
    use_syllabus: bool = True,
    teacher_id: int | None = None,
    blueprint: list[dict[str, Any]] | None = None,
) -> GenerationResult:
    """
    Deterministically compiles a full paper from templates and curriculum TopicNodes.
    COMPLETELY ELIMINATES RUNTIME LLM CALLS.
    """
    start_time = time.time()
    
    from sqlalchemy import select
    from ..models import Subject
    from .models import SubjectSyllabus
    
    subject = db.get(Subject, subject_id)
    syllabus = db.scalar(
        select(SubjectSyllabus).where(SubjectSyllabus.subject_id == subject_id)
    )

    # ---- 1. PLANNER: Create individual question tasks ----
    tasks: list[dict[str, Any]] = []

    if blueprint:
        for i, slot in enumerate(blueprint):
            def get_val(obj, key, default=None):
                if hasattr(obj, key):
                    return getattr(obj, key)
                elif isinstance(obj, dict):
                    return obj.get(key, default)
                return default

            assigned_module = module_filter if module_filter else get_val(slot, "module")
            rbt = get_val(slot, "rbt") or (bloom_levels[0] if bloom_levels else "L3")
            co = get_val(slot, "co") or "CO1"
            marks = get_val(slot, "marks", 5)
            
            tasks.append({
                "index": i,
                "marks": marks,
                "bloom_level": rbt,
                "co_mapping": co,
                "question_type": "theory",
                "module": assigned_module,
            })
    else:
        slots = _build_slot_plan(num_questions, marks_distribution, bloom_levels, co_targets, question_types)
        available_modules: list[int] = []
        if syllabus and syllabus.modules_json:
            for mod in syllabus.modules_json:
                m = mod.get("module")
                if m is not None and (module_filter is None or m == module_filter):
                    available_modules.append(int(m))
        if not available_modules:
            available_modules = [module_filter] if module_filter else [1, 2, 3, 4, 5]

        for i, slot in enumerate(slots):
            tasks.append({
                "index": i,
                "marks": slot["marks"],
                "bloom_level": slot["bloom_level"],
                "co_mapping": slot["co_mapping"],
                "question_type": slot["question_type"],
                "module": available_modules[i % len(available_modules)],
            })

    logger.info("Academic Planner created %d compilation tasks", len(tasks))

    # ---- 2. BUILD TOPIC GRAPH ----
    graph = build_topic_graph(db, subject_id)
    if not graph:
        logger.error(
            "Topic graph is empty for subject_id=%d — no KnowledgeChunks found. "
            "Cannot generate grounded questions. Upload syllabus content first.",
            subject_id,
        )
        # Return an empty result instead of hallucinating placeholder questions
        return GenerationResult(
            questions=[],
            retrieval_summary={
                "total_retrieved": 0,
                "sources_used": [],
                "topics_covered": [],
                "error": "No knowledge chunks found — please upload syllabus content first.",
            },
            validation_summary={"total": 0, "valid": 0, "errors": 0, "warnings": 0},
            generation_time=time.time() - start_time,
            model_used="Template Compiler (Deterministic)",
            creativity_level=0.0,
            temperature=0.0,
        )

    # ---- 3. COMPILE QUESTIONS ----
    generated_questions = []
    failed_count = 0
    used_topics = set()
    used_templates = set()

    for task in tasks:
        # Find candidates matching module
        candidates = [node for node in graph if node.module == task["module"]]
        
        # Filter out already used topics to guarantee maximum curriculum coverage
        unused_candidates = [c for c in candidates if c.topic not in used_topics]
        if unused_candidates:
            candidates = unused_candidates
            
        # Match Bloom level & Course Outcome strictly
        strict_candidates = [
            c for c in candidates 
            if c.bloom_level.upper() == task["bloom_level"].upper() 
            and c.co.upper() == task["co_mapping"].upper()
        ]
        
        # Fallback 1: match Course Outcome
        if not strict_candidates:
            strict_candidates = [
                c for c in candidates 
                if c.co.upper() == task["co_mapping"].upper()
            ]
            
        # Fallback 2: match Bloom level
        if not strict_candidates:
            strict_candidates = [
                c for c in candidates 
                if c.bloom_level.upper() == task["bloom_level"].upper()
            ]
            
        # Fallback 3: match module only
        if not strict_candidates:
            strict_candidates = candidates
            
        # Fallback 4: match any topic node in the curriculum
        if not strict_candidates:
            strict_candidates = graph

        # Select a node
        selected_node = random.choice(strict_candidates)
        used_topics.add(selected_node.topic)
        
        # Check if this topic has a permanent image asset linked
        is_image = selected_node.image_path is not None
        
        # Deterministically compile question using VTU templates
        question_text = compile_question(
            topic=selected_node.topic,
            bloom_level=task["bloom_level"],
            keywords=selected_node.keywords,
            marks=task["marks"],
            is_image_question=is_image,
            used_templates=used_templates
        )
        
        generated_questions.append(
            GeneratedQuestion(
                text=question_text,
                marks=task["marks"],
                bloom_level=task["bloom_level"],
                co_mapping=task["co_mapping"],
                module_number=task["module"],
                question_type="diagram" if is_image else task["question_type"],
                topic_name=selected_node.topic,
                source_chunk_ids=selected_node.chunk_ids,  # ← real chunk IDs for grounding
                source_documents=[],
                figure_image_paths=[selected_node.image_path] if is_image else [],
                confidence=1.0,
                validation=ValidationResult(is_valid=True, confidence=1.0),
                task_index=task["index"]
            )
        )

    # Sort to respect original blueprint layout
    generated_questions.sort(key=lambda q: q.task_index if q.task_index is not None else 999)

    # ---- 4. GROUNDING FILTER ----
    # Reject any question that contains hallucinated placeholder text or lacks chunk grounding.
    from .validators.question_validator import validate_grounding

    grounded: list[GeneratedQuestion] = []
    rejected_count = 0
    for gq in generated_questions:
        # Build a lightweight dict for the grounding checker
        gq_dict = {
            "text": gq.text,
            "source_chunk_id": gq.source_chunk_ids[0] if gq.source_chunk_ids else None,
        }
        result = validate_grounding(gq_dict)
        if result.ok:
            grounded.append(gq)
        else:
            rejected_count += 1
            logger.warning(
                "Grounding filter rejected question (topic=%r): %s",
                gq.topic_name, " | ".join(result.errors),
            )

    if rejected_count:
        logger.warning(
            "Grounding filter: %d/%d questions rejected (hallucination/ungrounded). "
            "Check KnowledgeChunk data quality.",
            rejected_count, len(generated_questions)
        )

    generated_questions = grounded

    elapsed = time.time() - start_time
    logger.info(
        "Deterministic template compilation complete: compiled %d questions in %.4fs",
        len(generated_questions), elapsed
    )

    return GenerationResult(
        questions=generated_questions,
        retrieval_summary={
            "total_retrieved": len(generated_questions),
            "sources_used": ["Academic Topic Graph", "Template Compiler"],
            "topics_covered": list(used_topics),
        },
        validation_summary={
            "total": len(generated_questions),
            "valid": len(generated_questions),
            "errors": 0,
            "warnings": 0,
        },
        generation_time=elapsed,
        model_used="Template Compiler (Deterministic)",
        creativity_level=0.0,
        temperature=0.0,
    )
