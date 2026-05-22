"""
Retrieval-Constrained Generation Engine (Phase 6).

CORE PRINCIPLE: The LLM NEVER generates from memory alone.
All questions MUST be sourced from retrieved academic chunks.

Pipeline:
  1. Receive generation request (subject, module, bloom, CO, marks)
  2. Retrieve relevant chunks from the knowledge base
  3. Build a constrained prompt with ONLY retrieved content
  4. Call LLM with strict instructions to use ONLY provided context
  5. Validate output against retrieved context (anti-hallucination)
  6. Return structured questions with full source traceability
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..config import settings
from ..llm_pipeline import LLMCall
from .retrieval import RetrievedContext, retrieve_for_generation, get_generation_sources, RetrievalError
from .style_profiles import VTU_PROFILE, get_creativity_level, get_temperature
from .validation import validate_question, ValidationResult

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
    confidence: float = 0.0
    # Validation
    validation: ValidationResult | None = None
    task_index: int | None = None


@dataclass
class GenerationResult:
    """Complete result of a retrieval-constrained generation run."""
    questions: list[GeneratedQuestion]
    retrieval_summary: dict[str, Any]
    validation_summary: dict[str, Any]
    generation_time: float
    model_used: str
    creativity_level: float
    temperature: float


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

# (System prompt moved inline to _generate_one_question for short per-task prompts)



def _build_generation_prompt(
    contexts: list[RetrievedContext],
    num_questions: int,
    marks_distribution: dict[int, int] | None,
    bloom_levels: list[str] | None,
    co_targets: list[str] | None,
    question_types: list[str] | None,
    module_filter: int | None,
    additional_instructions: str | None,
) -> str:
    """Build the constrained generation prompt with retrieved context."""
    # Format contexts with indices for traceability
    context_block = ""
    for i, ctx in enumerate(contexts):
        meta_parts = []
        if ctx.module_number is not None:
            meta_parts.append(f"M{ctx.module_number}")
        if ctx.topic_name:
            meta_parts.append(ctx.topic_name)
        if ctx.bloom_level:
            meta_parts.append(ctx.bloom_level)
        if ctx.co_mapping:
            meta_parts.append(ctx.co_mapping)
        meta_parts.append(f"src:{ctx.document_name}")

        meta_str = " | ".join(meta_parts)
        chunk_text = ctx.text.replace("\n", " ").strip()
        context_block += f"[{i}]({meta_str}) {chunk_text}\n"

    # Build constraints
    constraints: list[str] = []
    constraints.append(f"Generate exactly {num_questions} questions.")

    if marks_distribution:
        dist_str = ", ".join(f"{count}x {marks}-mark" for marks, count in marks_distribution.items())
        constraints.append(f"Marks distribution: {dist_str}")

    if bloom_levels:
        constraints.append(f"Bloom's taxonomy levels to cover: {', '.join(bloom_levels)}")

    if co_targets:
        constraints.append(f"Course Outcomes to cover: {', '.join(co_targets)}")

    if question_types:
        constraints.append(f"Question types: {', '.join(question_types)}")

    if module_filter:
        constraints.append(f"All questions MUST be from Module {module_filter}")

    if additional_instructions:
        constraints.append(f"Additional instructions: {additional_instructions}")

    constraints_block = "\n".join(f"- {c}" for c in constraints)

    # Extract visual markers injected by multimodal enriched text pipeline
    equations: list[str] = []
    figures: list[str] = []
    tables: list[str] = []
    for ctx in contexts:
        for eq in re.findall(r"\[EQUATION:\s*([^\]]+)\]", ctx.text):
            if eq.strip() and eq.strip() not in equations:
                equations.append(eq.strip()[:120])
        for fig in re.findall(r"\[FIGURE:\s*([^\]]+)\]", ctx.text):
            if fig.strip() and fig.strip() not in figures:
                figures.append(fig.strip()[:160])
        for tbl in re.findall(r"\[TABLE:\s*([^\]]+)\]", ctx.text):
            if tbl.strip() and tbl.strip() not in tables:
                tables.append(tbl.strip()[:120])

    visual_context = ""
    if equations:
        visual_context += "\nEQUATIONS IN SOURCE:\n" + "\n".join(f"  • {e}" for e in equations[:6])
    if figures:
        visual_context += "\nFIGURES IN SOURCE:\n" + "\n".join(f"  • {f}" for f in figures[:4])
    if tables:
        visual_context += "\nTABLES IN SOURCE:\n" + "\n".join(f"  • {t}" for t in tables[:4])

    visual_note = (
        "\nWhen equations or figures are referenced, incorporate them naturally "
        "(e.g. 'With reference to the equation...', 'Explain the diagram showing...')."
        if visual_context else ""
    )

    return f"""ACADEMIC CONTEXT (use ONLY this content):
{context_block}{visual_context}

GENERATION CONSTRAINTS:
{constraints_block}

Generate VTU-style questions based ONLY on the above context chunks.{visual_note}
For each question, include the source_indices array listing which CHUNK indices were used.
"""


def _topic_from_context(context: RetrievedContext) -> str:
    topic = ""
    if context.topic_name:
        topic = context.topic_name.strip()
    
    if not topic:
        topic = context.text.strip()
        first_sentence = re.split(r"(?<=[.!?])\s+", topic)[0].strip()
        topic = first_sentence

    # Remove page markers, equation/figure/table visual tags
    topic = re.sub(r"---\s*Page\s*\d+\s*---", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"\[(?:EQUATION|FIGURE|TABLE|IMAGE):[^\]]*\]", "", topic, flags=re.IGNORECASE)
    topic = re.sub(r"^---.*?---\s*", "", topic).strip()
    
    cleaned = re.sub(r"^\W+|\W+$", "", topic).strip()

    if cleaned and len(cleaned) > 8 and not re.match(r"^-+$", cleaned) and "page" not in cleaned.lower():
        return cleaned[:140]

    return "the uploaded academic material"


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
# Core generation function
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
    Generate questions using retrieval-constrained generation.

    This is the PRIMARY generation function. It:
    1. Retrieves relevant chunks from the knowledge base
    2. Builds a constrained prompt with ONLY retrieved content
    3. Calls the LLM with strict anti-hallucination instructions
    4. Validates each generated question against source context
    5. Returns structured questions with full traceability

    Args:
        db: Database session.
        subject_id: Target subject.
        num_questions: How many questions to generate.
        marks_distribution: e.g. {2: 5, 5: 3, 10: 2} = 5x2-mark, 3x5-mark, 2x10-mark.
        bloom_levels: Bloom levels to target (e.g. ["L1", "L2", "L3"]).
        co_targets: COs to cover (e.g. ["CO1", "CO2"]).
        question_types: Types (e.g. ["theory", "numerical"]).
        module_filter: Restrict to specific module.
        additional_instructions: Free-text instructions.
        creativity_override: Override auto creativity level (0.0–1.0).
        existing_questions: Existing question texts for dedup.
        teacher_id: Optional teacher ID to filter documents.

    Returns:
        GenerationResult with questions and metadata.
    """
    start = time.time()

    # ---- 1. Get source configuration ----
    profile_sources = get_generation_sources(db, subject_id)
    sources = {
        "use_notes": profile_sources["use_notes"] if use_notes is None else use_notes,
        "use_question_bank": (
            profile_sources["use_question_bank"]
            if use_question_bank is None
            else use_question_bank
        ),
        "use_previous_papers": (
            profile_sources["use_previous_papers"]
            if use_previous_papers is None
            else use_previous_papers
        ),
        "use_syllabus": profile_sources["use_syllabus"] if use_syllabus is None else use_syllabus,
    }

    # ---- 2. Build retrieval query focusing on technical topics/content ----
    from sqlalchemy import select
    from ..models import Subject
    from .models import SubjectSyllabus

    subject = db.get(Subject, subject_id)
    subject_name = subject.name if subject else ""

    syllabus = db.scalar(
        select(SubjectSyllabus).where(SubjectSyllabus.subject_id == subject_id)
    )

    topic_keywords: list[str] = []
    if syllabus and syllabus.modules_json:
        for mod in syllabus.modules_json:
            mod_num = mod.get("module")
            if module_filter is None or mod_num == module_filter:
                title = mod.get("title")
                if title:
                    topic_keywords.append(title)
                topics = mod.get("topics", [])
                if isinstance(topics, list):
                    topic_keywords.extend([str(t) for t in topics[:3]])
                elif isinstance(topics, str):
                    topic_keywords.append(topics)

    topic_str = " ".join(topic_keywords[:5]) if topic_keywords else ""

    query_parts: list[str] = []
    if subject_name:
        query_parts.append(subject_name)
    if topic_str:
        query_parts.append(topic_str)
    if module_filter:
        query_parts.append(f"Module {module_filter}")
    if additional_instructions:
        query_parts.append(additional_instructions)

    retrieval_query = " ".join(query_parts) if query_parts else "academic concepts all modules"

    # ---- Determine creativity and temperature ----
    target_bloom = bloom_levels[0] if bloom_levels else "L3"
    creativity = creativity_override if creativity_override is not None else get_creativity_level(target_bloom)
    temperature = get_temperature(creativity)

    # ---- 3. PLANNER: Create individual question tasks ----
    tasks: list[dict[str, Any]] = []

    if blueprint:
        for i, slot in enumerate(blueprint):
            # If the user passed a strict module_filter, override the blueprint module
            assigned_module = module_filter if module_filter else slot["module_number"]
            tasks.append({
                "index": i,
                "marks": slot["marks"],
                "bloom_level": slot.get("rbt", bloom_levels[0] if bloom_levels else "L3"),
                "co_mapping": slot.get("co", "CO1"),
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

    logger.info("Planner created %d question tasks across %d modules", len(tasks), len(set(t["module"] for t in tasks)))

    # ---- 4. CACHED RETRIEVAL: one retrieval per module ----
    retrieval_cache: dict[int, list[RetrievedContext]] = {}
    all_contexts: list[RetrievedContext] = []
    all_sources: list[str] = []
    all_topics: list[str] = []
    total_retrieved = 0

    modules_needed = sorted(set(t["module"] for t in tasks))
    for mod in modules_needed:
        mod_query_parts = list(query_parts)
        mod_query_parts.append(f"Module {mod}")
        mod_query = " ".join(mod_query_parts) if mod_query_parts else "academic concepts"

        try:
            retrieval = retrieve_for_generation(
                db, subject_id, mod_query,
                use_notes=sources.get("use_notes", True),
                use_question_bank=sources.get("use_question_bank", True),
                use_previous_papers=sources.get("use_previous_papers", False),
                use_syllabus=sources.get("use_syllabus", True),
                module_filter=mod,
                top_k=1,
                teacher_id=teacher_id,
            )
            retrieval_cache[mod] = retrieval.contexts
            all_contexts.extend(retrieval.contexts)
            all_sources.extend(retrieval.sources_used)
            all_topics.extend(retrieval.topics_covered)
            total_retrieved += retrieval.total_retrieved
            logger.info("Module %d: retrieved %d chunks (cached)", mod, len(retrieval.contexts))
        except Exception as e:
            logger.warning("Module %d: strict retrieval returned 0 chunks (%s). Trying fallback search without module constraint.", mod, e)
            try:
                retrieval = retrieve_for_generation(
                    db, subject_id, "academic concepts",
                    use_notes=True, use_question_bank=True,
                    use_previous_papers=False, use_syllabus=True,
                    module_filter=mod,
                    top_k=1,
                    teacher_id=teacher_id,
                )
                retrieval_cache[mod] = retrieval.contexts
                all_contexts.extend(retrieval.contexts)
                all_sources.extend(retrieval.sources_used)
                all_topics.extend(retrieval.topics_covered)
                total_retrieved += retrieval.total_retrieved
            except Exception:
                logger.warning("Module %d: both strict and fallback retrieval failed.", mod)
                retrieval_cache[mod] = []

    # If a module got 0 chunks, fall back to broadest retrieval
    if not all_contexts:
        try:
            broad = retrieve_for_generation(
                db, subject_id, retrieval_query,
                use_notes=True, use_question_bank=True,
                use_previous_papers=False, use_syllabus=True,
                top_k=5, teacher_id=teacher_id,
            )
            if not broad.contexts:
                return GenerationResult(
                    questions=[], retrieval_summary={"total_retrieved": 0, "error": "No relevant content found"},
                    validation_summary={"total": 0, "valid": 0, "errors": 0},
                    generation_time=time.time() - start, model_used="retrieval-empty",
                    creativity_level=0.0, temperature=0.1,
                )
            for mod in modules_needed:
                retrieval_cache[mod] = broad.contexts
            all_contexts = broad.contexts
            all_sources = broad.sources_used
            all_topics = broad.topics_covered
            total_retrieved = broad.total_retrieved
        except Exception as e:
            logger.error("Broad retrieval fallback failed: %s", e)
            return GenerationResult(
                questions=[], retrieval_summary={"total_retrieved": 0, "error": f"No relevant content found: {e}"},
                validation_summary={"total": 0, "valid": 0, "errors": 0},
                generation_time=time.time() - start, model_used="retrieval-empty",
                creativity_level=0.0, temperature=0.1,
            )

    for mod in modules_needed:
        if not retrieval_cache.get(mod):
            # Try to populate with any chunks from all_contexts that belong to this module first
            mod_chunks = [c for c in all_contexts if c.module_number == mod]
            if mod_chunks:
                retrieval_cache[mod] = mod_chunks
            else:
                retrieval_cache[mod] = all_contexts[:3]

    # ---- 5. SEMAPHORE-BOUNDED MICRO-BATCH PARALLEL GENERATION ----
    import os
    import math
    import random
    import threading
    from collections import defaultdict
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from .policies import RBT_VERBS
    from .sanitizer import sanitize_question_output

    # Default to 2 concurrent tasks to prevent Ollama GPU/CPU thrashing
    MAX_CONCURRENT = int(os.getenv("OLLAMA_NUM_PARALLEL", "2"))
    _semaphore = threading.Semaphore(MAX_CONCURRENT)

    llm = LLMCall(model=settings.ollama_model, timeout=settings.ollama_generation_timeout_seconds)
    model_used = settings.ollama_model
    llm_available = llm.is_available()

    if not llm_available:
        logger.warning("Ollama unavailable — using heuristic fallback for all tasks")

    # Group tasks by module to form micro-batches
    module_to_tasks = defaultdict(list)
    for t in tasks:
        module_to_tasks[t["module"]].append(t)

    micro_batches = []
    batch_index = 0
    for mod, mod_tasks in sorted(module_to_tasks.items()):
        # Split module tasks into small batches (max size 2) to keep context narrow and generation fast
        chunk_size = 2
        for idx in range(0, len(mod_tasks), chunk_size):
            chunk = mod_tasks[idx:idx + chunk_size]
            micro_batches.append({
                "index": batch_index,
                "module": mod,
                "tasks": chunk
            })
            batch_index += 1

    TASK_SYSTEM = (
        "You are an expert university question paper setter. Write university-level questions "
        "using ONLY the provided context. Do NOT use outside knowledge. Do NOT include markdown tags, "
        "bold headers, or meta labels. Output STRICTLY in JSON format with a 'questions' key containing a list of question objects:\n"
        '{"questions": [{"text": "...", "topic_name": "..."}]}'
    )

    # Load image chunks once
    import json
    from pathlib import Path
    image_chunks = []
    if Path("image_chunks.json").exists():
        try:
            with open("image_chunks.json", "r") as f:
                image_chunks = json.load(f)
        except Exception:
            pass

    def _generate_micro_batch(batch: dict[str, Any]) -> list[GeneratedQuestion]:
        """Generate a micro-batch of questions for a module, bounded by semaphore."""
        with _semaphore:
            mod = batch["module"]
            batch_tasks = batch["tasks"]

            # Strict Module Filtering
            contexts = [c for c in retrieval_cache.get(mod, []) if c.module_number == mod]
            if not contexts:
                logger.warning("Batch %d (Module %d) has no module-matching chunks in cache. Falling back to all retrieved contexts.", batch["index"], mod)
                contexts = retrieval_cache.get(mod, all_contexts[:3])
            if not contexts:
                return []

            ctx_block = ""
            for j, ctx in enumerate(contexts[:3]):
                snippet = ctx.text.replace("\n", " ").strip()[:500]
                ctx_block += f"[{j}] {snippet}\n"

            # Check if we need image context
            has_image_task = any(t.get("is_image_question") for t in batch_tasks)
            assigned_img_path = None
            if has_image_task and image_chunks:
                # Pick a random image chunk, preferably for this module (but we don't track module strictly in image_chunks right now, so just pick one)
                img = random.choice(image_chunks)
                assigned_img_path = img["image_path"]
                ctx_block += f"\n[IMAGE CONTEXT] Topic: {img['topic']}, Content: {img['caption']}\n"

            # Deterministic Action Verb enforcement from strict academic policies
            spec_lines = []
            for k, task in enumerate(batch_tasks, start=1):
                lvl = task["bloom_level"]
                verbs = RBT_VERBS.get(lvl, ["Explain"])
                verb = random.choice(verbs)
                is_img = task.get("is_image_question", False)
                type_str = "Image-based Question" if is_img else task['question_type']
                
                # We store the image path in the task so it can be picked up below
                if is_img and assigned_img_path:
                    task["figure_image_paths"] = [assigned_img_path]

                spec_lines.append(
                    f"Question {k}:\n"
                    f"- Marks: {task['marks']}\n"
                    f"- Bloom Level: {lvl} (MUST start with or use the action verb: '{verb}')\n"
                    f"- Topic Outcome: {task['co_mapping']}\n"
                    f"- Type: {type_str}"
                )

            specs_block = "\n\n".join(spec_lines)

            prompt = (
                f"CONTEXT:\n{ctx_block}\n"
                f"Generate exactly {len(batch_tasks)} distinct VTU-style questions based ONLY on the above context for Module {mod}.\n\n"
                f"SPECIFICATIONS FOR EACH QUESTION:\n{specs_block}\n\n"
                f"STRICT INSTRUCTIONS:\n"
                f"1. Return ONLY a JSON object containing the list of questions under the key 'questions', with each question having 'text' and 'topic_name' fields.\n"
                f"2. Every question MUST start with or use its targeted action verb for its Bloom level.\n"
                f"3. Each question MUST be a complete, grammatically correct sentence ending in proper punctuation.\n"
                f"4. The 'text' field MUST contain ONLY the final clean question text.\n"
                f"5. Do NOT include phrases like 'in the context of', 'considering', 'with reference to', or 'based on the provided text'.\n"
                f"6. Do NOT copy raw text fragments or chunk notes directly into the question.\n"
                f"7. Do NOT include:\n"
                f"   - reasoning or thought process\n"
                f"   - explanations or analysis\n"
                f"   - CO mappings or Bloom levels\n"
                f"   - metadata, formatting notes, or headings\n"
                f"   - markdown formatting or list numbers inside the text field\n"
            )
            if additional_instructions:
                prompt += f"\nNote: {additional_instructions}\n"

            # max_tokens of 150 per question is plenty. E.g. for batch of 3, 450 is extremely safe!
            max_predict = len(batch_tasks) * 150
            result = llm(
                prompt=prompt, system=TASK_SYSTEM,
                timeout=min(60.0, settings.ollama_generation_timeout_seconds),
                max_tokens=max_predict,
            )

            if not isinstance(result, dict) or not isinstance(result.get("questions"), list):
                logger.warning("Batch %d generation failed or returned invalid format. Result: %s", batch["index"], result)
                return []

            generated_questions = []
            returned_list = result["questions"]
            for idx, task in enumerate(batch_tasks):
                raw_text = ""
                topic = None
                if idx < len(returned_list) and isinstance(returned_list[idx], dict):
                    raw_text = returned_list[idx].get("text", "").strip()
                    topic = returned_list[idx].get("topic_name") or (contexts[0].topic_name if contexts else None)

                text = sanitize_question_output(raw_text)
                if not text:
                    raise ValueError(f"Failed to generate valid text for task {task['index']}")

                validation = validate_question(
                    question_text=text, marks=task["marks"], bloom_level=task["bloom_level"],
                    co_mapping=task["co_mapping"], retrieved_contexts=contexts,
                    existing_questions=existing_questions, topic_name=topic, module_number=mod,
                )

                generated_questions.append(
                    GeneratedQuestion(
                        text=text, marks=task["marks"], bloom_level=task["bloom_level"],
                        co_mapping=task["co_mapping"], module_number=mod,
                        question_type=task["question_type"], topic_name=topic,
                        source_chunk_ids=[contexts[0].chunk_id] if contexts else [],
                        source_documents=[contexts[0].document_name] if contexts else [],
                        confidence=validation.confidence, validation=validation,
                        task_index=task["index"],
                        figure_image_paths=task.get("figure_image_paths", []),
                    )
                )

            return generated_questions

    logger.info("Scheduling %d micro-batches (total required questions: %d), semaphore=%d", len(micro_batches), len(tasks), MAX_CONCURRENT)

    question_pool: list[GeneratedQuestion] = []
    failed_batches: list[dict[str, Any]] = []
    failed_count = 0

    if llm_available:
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
            future_to_batch = {pool.submit(_generate_micro_batch, b): b for b in micro_batches}

            for fut in as_completed(future_to_batch):
                batch_info = future_to_batch[fut]
                try:
                    batch_res = fut.result()
                    if batch_res:
                        question_pool.extend(batch_res)
                        logger.info(
                            "Batch %d OK: generated %d questions for Module %d (pool=%d/%d)",
                            batch_info["index"], len(batch_res), batch_info["module"], len(question_pool), num_questions
                        )
                    else:
                        failed_count += 1
                        failed_batches.append(batch_info)
                except Exception as exc:
                    failed_count += 1
                    failed_batches.append(batch_info)
                    logger.error("Batch %d failed: %s", batch_info["index"], exc)

        # ---- 8. RETRY: Failed batches ONLY ----
        if failed_batches:
            logger.info("Retrying %d failed batches...", len(failed_batches))
            with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
                future_to_batch = {pool.submit(_generate_micro_batch, b): b for b in failed_batches}
                for fut in as_completed(future_to_batch):
                    batch_info = future_to_batch[fut]
                    try:
                        batch_res = fut.result()
                        if batch_res:
                            question_pool.extend(batch_res)
                            logger.info("Retry Batch %d OK", batch_info["index"])
                    except Exception as exc:
                        logger.error("Retry Batch %d failed again: %s", batch_info["index"], exc)

    # ---- 9. DEDUPLICATION (fast Jaccard) ----
    seen_texts: list[str] = list(existing_questions or [])
    deduplicated: list[GeneratedQuestion] = []

    for gq in question_pool:
        is_dup = False
        gq_lower = gq.text.lower().strip()
        for seen in seen_texts:
            a_words = set(gq_lower.split())
            b_words = set(seen.lower().split())
            union = a_words | b_words
            if union and len(a_words & b_words) / len(union) > 0.7:
                is_dup = True
                break
        if not is_dup:
            deduplicated.append(gq)
            seen_texts.append(gq_lower)

    generated = deduplicated[:num_questions]

    # Ensure generated questions exactly map to the blueprint order
    generated.sort(key=lambda q: q.task_index if q.task_index is not None else 999)

    valid_count = sum(1 for q in generated if q.validation and q.validation.is_valid)
    error_count = sum(1 for q in generated if q.validation and not q.validation.is_valid)

    elapsed = time.time() - start
    logger.info(
        "Generation complete: %d questions in %.1fs | pool=%d deduped=%d failed=%d",
        len(generated), elapsed, len(question_pool), len(deduplicated),
        failed_count,
    )

    return GenerationResult(
        questions=generated,
        retrieval_summary={
            "total_retrieved": total_retrieved,
            "sources_used": list(set(all_sources)),
            "topics_covered": list(set(all_topics)),
        },
        validation_summary={
            "total": len(generated),
            "valid": valid_count,
            "errors": error_count,
            "warnings": sum(1 for q in generated if q.validation and q.validation.warnings),
            **({} if llm_available else {"llm_error": "Ollama is unavailable"}),
        },
        generation_time=elapsed,
        model_used=model_used,
        creativity_level=creativity,
        temperature=temperature,
    )
