from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...llm_pipeline import LLMCall
from ..models import ChunkApprovalStatus, KnowledgeChunk


@dataclass
class GenerationHealth:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    stats: dict[str, int | str] = field(default_factory=dict)


def run_generation_healthcheck(db: Session, *, subject_id: int, modules: list[int]) -> GenerationHealth:
    errors: list[str] = []
    warnings: list[str] = []
    stats: dict[str, int | str] = {"ollama_model": settings.ollama_model}

    if not LLMCall().is_available():
        errors.append(f"Ollama is not reachable at {settings.ollama_base_url}")

    approved_stmt = select(func.count(KnowledgeChunk.id)).where(
        KnowledgeChunk.subject_id == subject_id,
        KnowledgeChunk.approval_status.in_(
            [ChunkApprovalStatus.AUTO_APPROVED, ChunkApprovalStatus.APPROVED, ChunkApprovalStatus.EDITED]
        ),
    )
    total_approved = int(db.scalar(approved_stmt) or 0)
    stats["approved_chunks"] = total_approved
    if total_approved == 0:
        errors.append("No approved knowledge chunks are ready for generation")

    for module in modules or [1, 2, 3, 4, 5]:
        module_count = int(
            db.scalar(
                approved_stmt.where(KnowledgeChunk.module_number == module)
            )
            or 0
        )
        stats[f"module_{module}_chunks"] = module_count
        if module_count == 0:
            warnings.append(f"Module {module} has no approved chunks")

    embedded = int(
        db.scalar(
            select(func.count(KnowledgeChunk.id)).where(
                KnowledgeChunk.subject_id == subject_id,
                KnowledgeChunk.embedding_vector.is_not(None),
            )
        )
        or 0
    )
    stats["embedded_chunks"] = embedded
    if embedded == 0:
        warnings.append("No chunk embeddings found; retrieval will fall back to lexical ranking")

    return GenerationHealth(ok=not errors, errors=errors, warnings=warnings, stats=stats)
