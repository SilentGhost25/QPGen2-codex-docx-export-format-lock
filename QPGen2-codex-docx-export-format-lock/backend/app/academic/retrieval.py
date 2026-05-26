"""
Multi-source retrieval system for retrieval-constrained generation.

Retrieves relevant academic chunks from:
- Notes
- Question Banks
- Previous Papers
- Syllabus

Merges and ranks results before passing to the LLM.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .embeddings import cosine_similarity, generate_embedding
from .models import (
    AcademicDocument,
    ChunkApprovalStatus,
    DocumentType,
    KnowledgeChunk,
    QuestionGenerationProfile,
    SubjectSyllabus,
)

logger = logging.getLogger("app.academic.retrieval")


class RetrievalError(Exception):
    """Exception raised when academic retrieval fails or returns no chunks."""
    pass


def _normalize_chunk_key(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return normalized[:220]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievedContext:
    """A ranked chunk with source metadata for generation."""
    chunk_id: int
    text: str
    relevance_score: float
    source_type: str  # notes, question_bank, previous_paper, syllabus
    document_name: str
    module_number: int | None = None
    topic_name: str | None = None
    bloom_level: str | None = None
    co_mapping: str | None = None


@dataclass
class RetrievalResult:
    """Complete retrieval result for a generation request."""
    contexts: list[RetrievedContext]
    total_retrieved: int
    sources_used: list[str]
    topics_covered: list[str]


# ---------------------------------------------------------------------------
# Source type mapping
# ---------------------------------------------------------------------------

_DOC_TYPE_TO_SOURCE = {
    DocumentType.NOTES: "notes",
    DocumentType.QUESTION_BANK: "question_bank",
    DocumentType.PREVIOUS_PAPER: "previous_paper",
    DocumentType.SYLLABUS: "syllabus",
    DocumentType.LAB_MANUAL: "notes",
    DocumentType.PPT: "notes",
    DocumentType.OTHER: "notes",
}


# ---------------------------------------------------------------------------
# SimpleBM25 Retriever (Zero-Dependency)
# ---------------------------------------------------------------------------

class SimpleBM25:
    """Lightweight, pure-Python BM25 keyword ranker."""
    def __init__(self, corpus: list[str], k1: float = 1.5, b: float = 0.75):
        import math
        from collections import Counter
        self.k1 = k1
        self.b = b
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc.split()) for doc in corpus) / max(self.corpus_size, 1)
        self.doc_freqs = []
        self.doc_lengths = []
        self.nd = {}  # Word to number of docs containing word
        for doc in corpus:
            words = doc.lower().split()
            self.doc_lengths.append(len(words))
            frequencies = Counter(words)
            self.doc_freqs.append(frequencies)
            for word in frequencies:
                self.nd[word] = self.nd.get(word, 0) + 1

    def get_score(self, query: str, index: int) -> float:
        import math
        score = 0.0
        query_words = query.lower().split()
        doc_len = self.doc_lengths[index]
        freq = self.doc_freqs[index]
        for word in query_words:
            if word not in self.nd:
                continue
            n_q = self.nd[word]
            # IDF calculation
            idf = math.log(1.0 + (self.corpus_size - n_q + 0.5) / (n_q + 0.5))
            f_q = freq.get(word, 0)
            # BM25 formula
            numerator = f_q * (self.k1 + 1.0)
            denominator = f_q + self.k1 * (1.0 - self.b + self.b * (doc_len / max(self.avgdl, 1.0)))
            score += idf * (numerator / max(denominator, 0.0001))
        return score


# ---------------------------------------------------------------------------
# Multi-source retrieval
# ---------------------------------------------------------------------------

def retrieve_for_generation(
    db: Session,
    subject_id: int,
    query: str,
    *,
    use_notes: bool = True,
    use_question_bank: bool = True,
    use_previous_papers: bool = False,
    use_syllabus: bool = True,
    module_filter: int | None = None,
    bloom_filter: str | None = None,
    co_filter: str | None = None,
    top_k: int = 1,
    min_relevance: float = 0.25,
    teacher_id: int | None = None,
) -> RetrievalResult:
    """
    Retrieve relevant academic chunks for question generation.

    This is the core retrieval function that feeds the constrained LLM.

    Args:
        db: Database session.
        subject_id: Subject to retrieve from.
        query: Generation prompt / topic query.
        use_notes: Include notes chunks.
        use_question_bank: Include question bank chunks.
        use_previous_papers: Include previous paper chunks.
        use_syllabus: Include syllabus content.
        module_filter: Optional module number filter.
        bloom_filter: Optional Bloom level filter.
        co_filter: Optional CO filter.
        top_k: Max number of chunks to return.
        min_relevance: Minimum relevance score threshold.
        teacher_id: Optional teacher ID to restrict access.

    Returns:
        RetrievalResult with ranked contexts.
    """
    # Determine which document types to include
    allowed_types: set[DocumentType] = set()
    if use_notes:
        allowed_types.update({DocumentType.NOTES, DocumentType.LAB_MANUAL, DocumentType.PPT})
    if use_question_bank:
        allowed_types.add(DocumentType.QUESTION_BANK)
    if use_previous_papers:
        allowed_types.add(DocumentType.PREVIOUS_PAPER)
    if use_syllabus:
        allowed_types.add(DocumentType.SYLLABUS)

    if not allowed_types:
        return RetrievalResult(
            contexts=[], total_retrieved=0, sources_used=[], topics_covered=[]
        )

    # Get document IDs for allowed types
    doc_ids_stmt = (
        select(AcademicDocument.id, AcademicDocument.document_type, AcademicDocument.file_name)
        .where(
            AcademicDocument.subject_id == subject_id,
            AcademicDocument.document_type.in_(allowed_types),
        )
    )
    
    t_doc_ids_stmt = doc_ids_stmt
    if teacher_id is not None:
        t_doc_ids_stmt = doc_ids_stmt.where(AcademicDocument.uploaded_by == teacher_id)

    doc_rows = db.execute(t_doc_ids_stmt).all()
    if not doc_rows and teacher_id is not None:
        logger.info(
            "No academic documents found uploaded by teacher_id=%d for subject_id=%d; falling back to all subject uploads",
            teacher_id,
            subject_id,
        )
        doc_rows = db.execute(doc_ids_stmt).all()

    doc_info = {row.id: (row.document_type, row.file_name) for row in doc_rows}

    if not doc_info:
        return RetrievalResult(
            contexts=[], total_retrieved=0, sources_used=[], topics_covered=[]
        )

    # Fetch approved chunks from allowed documents
    chunks_stmt = (
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.subject_id == subject_id,
            KnowledgeChunk.document_id.in_(doc_info.keys()),
            KnowledgeChunk.approval_status.in_([
                ChunkApprovalStatus.AUTO_APPROVED,
                ChunkApprovalStatus.APPROVED,
                ChunkApprovalStatus.EDITED,
                ChunkApprovalStatus.PENDING_REVIEW,
            ]),
        )
    )

    if bloom_filter:
        chunks_stmt = chunks_stmt.where(KnowledgeChunk.bloom_level == bloom_filter)
    if co_filter:
        chunks_stmt = chunks_stmt.where(KnowledgeChunk.co_mapping == co_filter)
    if module_filter is not None:
        chunks_stmt = chunks_stmt.where(KnowledgeChunk.module_number == module_filter)

    chunks = list(db.scalars(chunks_stmt))

    if not chunks:
        return RetrievalResult(
            contexts=[], total_retrieved=0, sources_used=[], topics_covered=[]
        )

    query_embedding = None
    if any(chunk.embedding_vector for chunk in chunks):
        query_embedding = generate_embedding(query)

    # Pre-compute BM25 scores for keyword hybrid ranking
    bm25_scores = []
    try:
        bm25 = SimpleBM25([c.chunk_text for c in chunks])
        raw_bm25 = [bm25.get_score(query, idx) for idx in range(len(chunks))]
        max_bm25 = max(raw_bm25) if raw_bm25 else 0.0
        if max_bm25 > 0.0:
            bm25_scores = [s / max_bm25 for s in raw_bm25]
        else:
            bm25_scores = [0.0] * len(chunks)
    except Exception as e:
        logger.error("Failed BM25 indexing/scoring: %s", e)
        bm25_scores = [0.0] * len(chunks)

    # Score and rank chunks
    scored_contexts: list[RetrievedContext] = []

    for idx, chunk in enumerate(chunks):
        doc_type, doc_name = doc_info.get(chunk.document_id, (DocumentType.NOTES, "Unknown"))
        source_type = _DOC_TYPE_TO_SOURCE.get(doc_type, "notes")

        # Compute vector relevance score
        vector_score = 0.0
        if query_embedding and chunk.embedding_vector:
            vector_score = cosine_similarity(query_embedding, chunk.embedding_vector)
        else:
            # Text-based fallback
            query_lower = query.lower()
            chunk_lower = chunk.chunk_text.lower()
            query_words = set(query_lower.split())
            chunk_words = set(chunk_lower.split())
            overlap = len(query_words & chunk_words)
            vector_score = min(1.0, overlap / max(len(query_words), 1) * 0.8)

        # Retrieve scaled BM25 score
        bm25_score = bm25_scores[idx] if bm25_scores else 0.0

        # Hybrid search combination (70% Semantic Vector + 30% BM25 keyword matching)
        score = 0.7 * vector_score + 0.3 * bm25_score

        # Boost scores
        if chunk.confidence_score >= 0.7:
            score *= 1.1
        if source_type == "notes":
            score *= 1.25  # High priority for notes/PPTs/manuals (core knowledge base)
        elif source_type == "syllabus":
            score *= 1.20  # High priority for syllabus
        elif source_type == "question_bank":
            score *= 0.85  # De-prioritize pre-uploaded question banks to encourage new generation
        elif source_type == "previous_paper":
            score *= 0.80  # De-prioritize old papers
        if module_filter is not None:
            if chunk.module_number == module_filter:
                score *= 1.25
            elif chunk.module_number is not None:
                score *= 0.7

        if score < min_relevance:
            continue

        scored_contexts.append(RetrievedContext(
            chunk_id=chunk.id,
            text=chunk.chunk_text,
            relevance_score=round(score, 4),
            source_type=source_type,
            document_name=doc_name,
            module_number=chunk.module_number,
            topic_name=chunk.topic_name,
            bloom_level=chunk.bloom_level,
            co_mapping=chunk.co_mapping,
        ))

    # Sort by hybrid relevance
    scored_contexts.sort(key=lambda c: c.relevance_score, reverse=True)

    # Technical Alignment Cross-Encoder Reranking
    from ..models import Subject
    subject = db.get(Subject, subject_id)
    subject_name = subject.name if subject else ""

    query_terms = set(re.findall(r"\b\w{3,}\b", query.lower()))
    if query_terms and scored_contexts:
        for context in scored_contexts:
            text_lower = context.text.lower()
            # Technical term matching density
            matched = sum(1 for term in query_terms if term in text_lower)
            density = matched / len(query_terms)

            # Bonus for subject matching
            subj_bonus = 0.15 if subject_name and subject_name.lower() in text_lower else 0.0

            # Adjust score with 35% weight given to technical alignment
            context.relevance_score = round(context.relevance_score * 0.65 + (density + subj_bonus) * 0.35, 4)

        # Re-sort by technical rerank score
        scored_contexts.sort(key=lambda c: c.relevance_score, reverse=True)
    deduped_contexts: list[RetrievedContext] = []
    seen_keys: set[str] = set()
    for context in scored_contexts:
        key = _normalize_chunk_key(context.text)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped_contexts.append(context)
        if len(deduped_contexts) >= top_k:
            break
    top_contexts = deduped_contexts

    # Step 4: Add Real Retrieval Logging (Highly Visible Debug Boundaries)
    logger.info("=" * 80)
    logger.info("USER QUERY: %s", query)

    for idx, doc in enumerate(top_contexts):
        logger.info("[DOC %d]", idx)
        logger.info("CONTENT: %s", doc.text[:500])
        logger.info("METADATA: type=%s, doc=%s, score=%f, module=%s", doc.source_type, doc.document_name, doc.relevance_score, doc.module_number)

    scores = [c.relevance_score for c in top_contexts]
    logger.info("SIMILARITY SCORES: %s", scores)
    logger.info("=" * 80)

    # Step 5: Remove silent fallbacks when retrieval is empty
    if not top_contexts:
        logger.error("Retrieval returned 0 chunks for query: '%s'", query)
        raise RetrievalError(f"No relevant academic content found in the knowledge base matching: '{query}'. Please make sure you have uploaded and approved notes, syllabus, or previous papers.")

    # Collect metadata
    sources_used = sorted(set(c.source_type for c in top_contexts))
    topics_covered = sorted(set(c.topic_name for c in top_contexts if c.topic_name))

    return RetrievalResult(
        contexts=top_contexts,
        total_retrieved=len(top_contexts),
        sources_used=sources_used,
        topics_covered=topics_covered,
    )


def get_generation_sources(
    db: Session, subject_id: int
) -> dict[str, bool]:
    """Get the configured source toggles for a subject."""
    profile = db.scalar(
        select(QuestionGenerationProfile).where(
            QuestionGenerationProfile.subject_id == subject_id
        )
    )
    if profile:
        return {
            "use_notes": profile.use_notes,
            "use_question_bank": profile.use_question_bank,
            "use_previous_papers": profile.use_previous_papers,
            "use_syllabus": profile.use_syllabus,
        }
    return {
        "use_notes": True,
        "use_question_bank": True,
        "use_previous_papers": False,
        "use_syllabus": True,
    }
