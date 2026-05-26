"""
API routes for the Academic Knowledge Intelligence Layer.

Provides endpoints for:
- Document upload and ingestion
- Knowledge chunk management (list, search, approve, edit)
- Syllabus management
- Generation profile configuration
- Topic coverage analytics
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..config import settings
from ..database import get_db
from ..models import Role, Subject, User, TeacherSubject, Question, QuestionPaper
from .embeddings import generate_embedding, generate_embeddings_batch
from .ingestion import create_document_record, process_document_background
from .models import (
    AcademicDocument,
    ChunkApprovalStatus,
    DocumentType,
    KnowledgeChunk,
    ProcessingStatus,
    QuestionGenerationProfile,
    SubjectSyllabus,
)
from .schemas import (
    AcademicDocumentListResponse,
    AcademicDocumentResponse,
    ChunkApprovalRequest,
    ChunkEditRequest,
    ChunkSearchResponse,
    GenerationProfileResponse,
    GenerationProfileUpdate,
    KnowledgeChunkResponse,
    RAGGeneratedQuestionResponse,
    RAGGenerationRequest,
    RAGGenerationResponse,
    StructuredContentResponse,
    SubjectSyllabusResponse,
    SyllabusUploadRequest,
    TopicCoverageItem,
    TopicCoverageResponse,
    AnalyticsDashboardResponse,
)

logger = logging.getLogger("app.academic.routes")

router = APIRouter(prefix="/api/v1/academic", tags=["academic"])


def check_subject_access(db: Session, user: User, subject_id: int) -> None:
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    if user.role == Role.TEACHER:
        # Check if the teacher is assigned to this subject
        assigned = db.scalar(
            select(TeacherSubject).where(
                TeacherSubject.teacher_id == user.id,
                TeacherSubject.subject_id == subject_id
            )
        )
        if not assigned:
            raise HTTPException(status_code=403, detail="Subject access denied")
    elif user.role == Role.HOD and user.dept_id:
        if user.dept_id != subject.dept_id:
            raise HTTPException(status_code=403, detail="Department access denied")


# ---------------------------------------------------------------------------
# Document Upload
# ---------------------------------------------------------------------------

@router.post("/documents/upload", response_model=AcademicDocumentResponse)
async def upload_academic_document(
    background_tasks: BackgroundTasks,
    subject_id: int = Form(...),
    document_type: str = Form("notes"),
    file: UploadFile = File(...),
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> AcademicDocumentResponse:
    """Upload and ingest an academic document."""
    # Validate subject
    check_subject_access(db, user, subject_id)

    # Validate file type
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    allowed = {".pdf", ".docx", ".pptx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
    if suffix not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Allowed: {', '.join(sorted(allowed))}",
        )

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    # Parse document type
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        doc_type = DocumentType.NOTES

    # Create the record immediately and return
    doc = create_document_record(
        db=db,
        subject_id=subject_id,
        user_id=user.id,
        file_name=filename,
        content=content,
        document_type=doc_type,
    )

    if len(content) <= settings.academic_sync_processing_limit_bytes:
        process_document_background(doc.id)
        db.refresh(doc)
        logger.info("Processed document %d inline for immediate retrieval readiness", doc.id)
    else:
        background_tasks.add_task(process_document_background, doc.id)
        logger.info("Queued background processing for document %d", doc.id)

    return AcademicDocumentResponse.model_validate(doc)


def _generate_chunk_embeddings_bg(document_id: int) -> None:
    """Generate embeddings for all chunks of a document (background task).
    
    Creates its own database session since this runs outside the request context.
    """
    from ..database import SessionLocal
    
    db = SessionLocal()
    try:
        _generate_chunk_embeddings(db, document_id)
    finally:
        db.close()


def _generate_chunk_embeddings(db: Session, document_id: int) -> None:
    """Generate embeddings for all chunks of a document."""
    chunks = list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document_id)
            .order_by(KnowledgeChunk.chunk_index)
        )
    )
    if not chunks:
        return

    texts = [c.chunk_text for c in chunks]
    embeddings = generate_embeddings_batch(texts)

    for chunk, embedding in zip(chunks, embeddings):
        if embedding is not None:
            chunk.embedding_vector = embedding

    db.commit()
    logger.info("Generated embeddings for %d chunks (doc=%d)", len(chunks), document_id)


# ---------------------------------------------------------------------------
# Document Listing
# ---------------------------------------------------------------------------

@router.get("/documents", response_model=AcademicDocumentListResponse)
def list_academic_documents(
    subject_id: int | None = None,
    document_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """List academic documents with optional filters."""
    stmt = select(AcademicDocument).order_by(AcademicDocument.created_at.desc())

    if subject_id:
        stmt = stmt.where(AcademicDocument.subject_id == subject_id)
    if document_type:
        try:
            stmt = stmt.where(AcademicDocument.document_type == DocumentType(document_type))
        except ValueError:
            pass

    # Access control
    if user.role == Role.TEACHER:
        stmt = stmt.where(AcademicDocument.uploaded_by == user.id)
    elif user.role == Role.HOD and user.dept_id:
        subject_ids = select(Subject.id).where(Subject.dept_id == user.dept_id)
        stmt = stmt.where(AcademicDocument.subject_id.in_(subject_ids))

    docs = list(db.scalars(stmt))
    return {"documents": docs, "total": len(docs)}


@router.delete("/documents/{document_id}", status_code=200)
def delete_academic_document(
    document_id: int,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """Delete an academic document and its chunks."""
    doc = db.get(AcademicDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if user.role == Role.TEACHER and doc.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this document")

    db.delete(doc)
    db.commit()
    return {"deleted": True, "document_id": document_id}


@router.post("/reindex", status_code=200)
def reindex_all_documents(
    background_tasks: BackgroundTasks,
    user: User = Depends(require_roles(Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """
    Force full reindexing of all academic documents:
    Delete old chunks, rechunk, re-generate embeddings, and auto-approve chunks.
    Runs asynchronously in the background.
    """
    # 1. Fetch all documents
    docs = list(db.scalars(select(AcademicDocument)))
    if not docs:
        return {"message": "No documents found to reindex"}
        
    doc_ids = [d.id for d in docs]
    
    def run_reindex_bg():
        from ..database import SessionLocal
        from .ingestion import process_document_background
        from sqlalchemy import delete
        from ..models import Question
        
        bg_db = SessionLocal()
        try:
            for doc_id in doc_ids:
                logger.info(f"Background task starting reindexing for document_id={doc_id}")
                try:
                    # Clean up existing chunks and questions related to this document
                    bg_db.execute(
                        delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc_id)
                    )
                    bg_db.execute(
                        delete(Question).where(Question.source_doc_id == doc_id)
                    )
                    bg_db.commit()
                    
                    # The ingestion pipeline automatically recreates everything with auto-approval
                    process_document_background(doc_id)
                except Exception as ex:
                    logger.error(f"Failed to reindex document_id={doc_id}: {ex}")
        finally:
            bg_db.close()
            
    background_tasks.add_task(run_reindex_bg)
    return {
        "message": f"Successfully queued reindexing for {len(doc_ids)} documents",
        "document_ids": doc_ids,
    }



@router.get("/documents/{document_id}/structured", response_model=StructuredContentResponse)
def get_structured_content(
    document_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Return the full structured visual content for a document.

    The structured content is a JSON object with:
      - pages[].blocks[] — each block typed as heading/paragraph/equation/figure/table
      - summary — counts and feature flags (has_equations, has_figures, has_tables)

    If the document has not yet been processed or multimodal parsing failed,
    structured_content will be null.
    """
    doc = db.get(AcademicDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Access control
    if user.role == Role.TEACHER and doc.uploaded_by != user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    elif user.role == Role.HOD and user.dept_id:
        from sqlalchemy import select as sa_select
        from ..models import Subject
        subject = db.get(Subject, doc.subject_id)
        if subject and subject.dept_id != user.dept_id:
            raise HTTPException(status_code=403, detail="Department access denied")

    return {
        "document_id": doc.id,
        "file_name": doc.file_name,
        "processing_status": doc.processing_status,
        "structured_content": doc.structured_content,
        "has_equations": doc.has_equations,
        "has_figures": doc.has_figures,
        "has_tables": doc.has_tables,
        "equation_count": doc.equation_count,
        "figure_count": doc.figure_count,
        "table_count": doc.table_count,
    }


# ---------------------------------------------------------------------------
# Knowledge Chunks
# ---------------------------------------------------------------------------

@router.get("/chunks", response_model=list[KnowledgeChunkResponse])
def list_knowledge_chunks(
    document_id: int | None = None,
    subject_id: int | None = None,
    module_number: int | None = None,
    approval_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list:
    """List knowledge chunks with filtering."""
    stmt = select(KnowledgeChunk).order_by(
        KnowledgeChunk.document_id, KnowledgeChunk.chunk_index
    )

    if document_id:
        stmt = stmt.where(KnowledgeChunk.document_id == document_id)
    if subject_id:
        stmt = stmt.where(KnowledgeChunk.subject_id == subject_id)
    if module_number:
        stmt = stmt.where(KnowledgeChunk.module_number == module_number)
    if approval_status:
        try:
            stmt = stmt.where(
                KnowledgeChunk.approval_status == ChunkApprovalStatus(approval_status)
            )
        except ValueError:
            pass

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt))


@router.get("/chunks/search", response_model=ChunkSearchResponse)
def search_knowledge_chunks(
    query: str,
    subject_id: int | None = None,
    module_number: int | None = None,
    limit: int = 20,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Semantic search across knowledge chunks."""
    # Generate query embedding
    query_embedding = generate_embedding(query)

    # Build base filter
    stmt = select(KnowledgeChunk)
    if subject_id:
        stmt = stmt.where(KnowledgeChunk.subject_id == subject_id)
    if module_number:
        stmt = stmt.where(KnowledgeChunk.module_number == module_number)

    # Only search approved/auto-approved chunks
    stmt = stmt.where(
        KnowledgeChunk.approval_status.in_([
            ChunkApprovalStatus.AUTO_APPROVED,
            ChunkApprovalStatus.APPROVED,
            ChunkApprovalStatus.EDITED,
            ChunkApprovalStatus.PENDING_REVIEW,
        ])
    )

    all_chunks = list(db.scalars(stmt))

    if query_embedding and all_chunks:
        # Semantic search using embeddings
        from .embeddings import cosine_similarity

        scored = []
        for chunk in all_chunks:
            if chunk.embedding_vector:
                score = cosine_similarity(query_embedding, chunk.embedding_vector)
                scored.append((chunk, score))
            else:
                # Fallback: text matching
                if query.lower() in chunk.chunk_text.lower():
                    scored.append((chunk, 0.5))

        scored.sort(key=lambda x: x[1], reverse=True)
        results = [c for c, _ in scored[:limit]]
    else:
        # Text-based fallback search
        stmt = stmt.where(KnowledgeChunk.chunk_text.ilike(f"%{query}%"))
        results = list(db.scalars(stmt.limit(limit)))

    return {"chunks": results, "total": len(results), "query": query}


@router.put("/chunks/{chunk_id}/approve")
def approve_chunk(
    chunk_id: int,
    payload: ChunkApprovalRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> KnowledgeChunkResponse:
    """Approve or reject a knowledge chunk."""
    chunk = db.get(KnowledgeChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    chunk.approval_status = payload.approval_status
    chunk.reviewed_by = user.id
    chunk.review_notes = payload.review_notes
    db.commit()
    db.refresh(chunk)
    return KnowledgeChunkResponse.model_validate(chunk)


@router.put("/chunks/{chunk_id}/edit")
def edit_chunk(
    chunk_id: int,
    payload: ChunkEditRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> KnowledgeChunkResponse:
    """Edit a knowledge chunk's content or metadata."""
    chunk = db.get(KnowledgeChunk, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")

    if payload.chunk_text is not None:
        chunk.chunk_text = payload.chunk_text
        # Re-generate embedding
        new_embedding = generate_embedding(payload.chunk_text)
        if new_embedding:
            chunk.embedding_vector = new_embedding
    if payload.module_number is not None:
        chunk.module_number = payload.module_number
    if payload.topic_name is not None:
        chunk.topic_name = payload.topic_name
    if payload.bloom_level is not None:
        chunk.bloom_level = payload.bloom_level
    if payload.co_mapping is not None:
        chunk.co_mapping = payload.co_mapping

    chunk.approval_status = ChunkApprovalStatus.EDITED
    chunk.reviewed_by = user.id
    db.commit()
    db.refresh(chunk)
    return KnowledgeChunkResponse.model_validate(chunk)


# ---------------------------------------------------------------------------
# Syllabus Management
# ---------------------------------------------------------------------------

@router.post("/syllabus", response_model=SubjectSyllabusResponse)
def upload_syllabus(
    payload: SyllabusUploadRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> SubjectSyllabus:
    """Create or update a subject syllabus."""
    check_subject_access(db, user, payload.subject_id)

    existing = db.scalar(
        select(SubjectSyllabus).where(SubjectSyllabus.subject_id == payload.subject_id)
    )

    if existing:
        if payload.syllabus_text is not None:
            existing.syllabus_text = payload.syllabus_text
        if payload.modules is not None:
            existing.modules_json = [m.model_dump() for m in payload.modules]
        if payload.co_definitions is not None:
            existing.co_json = payload.co_definitions
        if payload.rbt_rules is not None:
            existing.rbt_rules = payload.rbt_rules
        db.commit()
        db.refresh(existing)
        return existing

    syllabus = SubjectSyllabus(
        subject_id=payload.subject_id,
        syllabus_text=payload.syllabus_text,
        modules_json=[m.model_dump() for m in payload.modules] if payload.modules else None,
        co_json=payload.co_definitions,
        rbt_rules=payload.rbt_rules,
        uploaded_by=user.id,
    )
    db.add(syllabus)
    db.commit()
    db.refresh(syllabus)
    return syllabus


@router.get("/syllabus/{subject_id}", response_model=SubjectSyllabusResponse)
def get_syllabus(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubjectSyllabus:
    """Get syllabus for a subject."""
    check_subject_access(db, user, subject_id)
    syllabus = db.scalar(
        select(SubjectSyllabus).where(SubjectSyllabus.subject_id == subject_id)
    )
    if not syllabus:
        raise HTTPException(status_code=404, detail="Syllabus not found for this subject")
    return syllabus


# ---------------------------------------------------------------------------
# Generation Profile
# ---------------------------------------------------------------------------

@router.get("/profile/{subject_id}", response_model=GenerationProfileResponse)
def get_generation_profile(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionGenerationProfile:
    """Get or create generation profile for a subject."""
    check_subject_access(db, user, subject_id)
    profile = db.scalar(
        select(QuestionGenerationProfile).where(
            QuestionGenerationProfile.subject_id == subject_id
        )
    )
    if not profile:
        profile = QuestionGenerationProfile(subject_id=subject_id)
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


@router.put("/profile/{subject_id}", response_model=GenerationProfileResponse)
def update_generation_profile(
    subject_id: int,
    payload: GenerationProfileUpdate,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> QuestionGenerationProfile:
    """Update generation profile for a subject."""
    check_subject_access(db, user, subject_id)
    profile = db.scalar(
        select(QuestionGenerationProfile).where(
            QuestionGenerationProfile.subject_id == subject_id
        )
    )
    if not profile:
        profile = QuestionGenerationProfile(subject_id=subject_id)
        db.add(profile)
        db.flush()

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(profile, field, value)

    db.commit()
    db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
# Topic Coverage Analytics
# ---------------------------------------------------------------------------

@router.get("/coverage/{subject_id}", response_model=TopicCoverageResponse)
def get_topic_coverage(
    subject_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get topic coverage analysis for a subject."""
    check_subject_access(db, user, subject_id)
    # Total counts
    total_chunks = db.scalar(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.subject_id == subject_id
        )
    ) or 0

    total_docs = db.scalar(
        select(func.count(AcademicDocument.id)).where(
            AcademicDocument.subject_id == subject_id
        )
    ) or 0

    # Coverage by module and topic
    coverage_query = (
        select(
            KnowledgeChunk.module_number,
            KnowledgeChunk.topic_name,
            func.count(KnowledgeChunk.id).label("chunk_count"),
            func.count(func.distinct(KnowledgeChunk.document_id)).label("doc_count"),
            func.avg(KnowledgeChunk.confidence_score).label("avg_conf"),
        )
        .where(KnowledgeChunk.subject_id == subject_id)
        .group_by(KnowledgeChunk.module_number, KnowledgeChunk.topic_name)
        .order_by(KnowledgeChunk.module_number)
    )

    rows = db.execute(coverage_query).all()
    coverage = [
        TopicCoverageItem(
            module_number=row.module_number or 0,
            topic_name=row.topic_name or "Unclassified",
            chunk_count=row.chunk_count,
            document_count=row.doc_count,
            avg_confidence=round(float(row.avg_conf or 0), 3),
        )
        for row in rows
    ]

    # Gap detection
    gaps: list[str] = []
    covered_modules = {item.module_number for item in coverage if item.module_number}
    for module in range(1, 6):
        if module not in covered_modules:
            gaps.append(f"Module {module} has no content chunks")
    
    low_coverage = [
        item for item in coverage if item.chunk_count < 3
    ]
    for item in low_coverage:
        gaps.append(f"Module {item.module_number} topic '{item.topic_name}' has only {item.chunk_count} chunk(s)")

    return {
        "subject_id": subject_id,
        "total_chunks": total_chunks,
        "total_documents": total_docs,
        "coverage": coverage,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# Retrieval-Constrained Generation (Phase 6)
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=None)
def generate_questions_rag(
    payload: RAGGenerationRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    """
    Generate questions using retrieval-constrained generation.

    The LLM NEVER generates from memory. All output is:
    1. Sourced from retrieved academic chunks
    2. Validated against the knowledge base
    3. Traced back to source documents

    Returns questions with full traceability and validation results.
    """
    from .generation import generate_questions_from_retrieval
    from .retrieval import RetrievalError

    # Validate subject exists and user has access
    check_subject_access(db, user, payload.subject_id)

    # Check we have content to generate from
    chunk_count = db.scalar(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.subject_id == payload.subject_id,
            KnowledgeChunk.approval_status.in_([
                ChunkApprovalStatus.AUTO_APPROVED,
                ChunkApprovalStatus.APPROVED,
                ChunkApprovalStatus.EDITED,
                ChunkApprovalStatus.PENDING_REVIEW,
            ]),
        )
    ) or 0

    if chunk_count == 0:
        raise HTTPException(
            status_code=400,
            detail="No approved knowledge chunks found for this subject. Upload and approve academic materials first.",
        )

    teacher_id = user.id if user.role == Role.TEACHER else None
    try:
        result = generate_questions_from_retrieval(
            db=db,
            subject_id=payload.subject_id,
            num_questions=payload.num_questions,
            marks_distribution=payload.marks_distribution,
            bloom_levels=payload.bloom_levels,
            co_targets=payload.co_targets,
            question_types=payload.question_types,
            module_filter=payload.module_filter,
            additional_instructions=payload.additional_instructions,
            creativity_override=payload.creativity_override,
            existing_questions=payload.existing_question_texts,
            teacher_id=teacher_id,
        )
    except RetrievalError as e:
        logger.exception("Retrieval failed during generation")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    # Build response — serialize ValidationIssue objects to strings
    from .sanitizer import sanitize_question_output
    questions_out = []
    for q in result.questions:
        cleaned_text = sanitize_question_output(q.text)
        questions_out.append(
            RAGGeneratedQuestionResponse(
                text=cleaned_text,
                marks=q.marks,
                bloom_level=q.bloom_level,
                co_mapping=q.co_mapping,
                module_number=q.module_number,
                question_type=q.question_type,
                topic_name=q.topic_name,
                source_chunk_ids=q.source_chunk_ids,
                source_documents=q.source_documents,
                confidence=q.confidence,
                is_valid=q.validation.is_valid if q.validation else True,
                validation_errors=[i.message for i in q.validation.errors] if q.validation else [],
                validation_warnings=[i.message for i in q.validation.warnings] if q.validation else [],
            )
        )

    return RAGGenerationResponse(
        questions=questions_out,
        retrieval_summary=result.retrieval_summary,
        validation_summary=result.validation_summary,
        generation_time=result.generation_time,
        model_used=result.model_used,
        creativity_level=result.creativity_level,
        temperature=result.temperature,
    ).model_dump()


# ---------------------------------------------------------------------------
# Analytics Dashboard (Phase 6)
# ---------------------------------------------------------------------------

@router.get("/analytics", response_model=AnalyticsDashboardResponse)
def get_academic_analytics(
    subject_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get consolidated academic and question-generation analytics for Teacher/HOD.
    Executes 6 COUNT/aggregate queries with role-based filtering:
    - Teacher: Filter by user.id
    - HOD: Filter by department-wide data (user.dept_id)
    - Admin: No filter
    """
    # 1. Base Query Construction
    # Q1: Chunk count by module
    q1_stmt = select(KnowledgeChunk.module_number, func.count(KnowledgeChunk.id))
    
    # Q2: Question count by Bloom level
    q2_stmt = select(Question.bloom_level, func.count(Question.id))
    
    # Q3: Question count by CO mapping
    q3_stmt = select(Question.course_outcome, func.count(Question.id))
    
    # Q4: Total papers semester
    q4_stmt = select(func.count(QuestionPaper.id))
    
    # Q5: Questions by module (for coverage gap analysis)
    q5_stmt = select(Question.module_number, func.count(Question.id))

    # Apply filters based on roles and optional subject_id
    if user.role == Role.TEACHER:
        # Filter chunks by teacher's documents
        q1_stmt = q1_stmt.join(AcademicDocument, KnowledgeChunk.document_id == AcademicDocument.id).where(AcademicDocument.uploaded_by == user.id)
        # Filter questions and papers by teacher
        q2_stmt = q2_stmt.where(Question.teacher_id == user.id)
        q3_stmt = q3_stmt.where(Question.teacher_id == user.id)
        q4_stmt = q4_stmt.where(QuestionPaper.teacher_id == user.id)
        q5_stmt = q5_stmt.where(Question.teacher_id == user.id)
    elif user.role == Role.HOD and user.dept_id:
        # Filter by department via Subject table
        q1_stmt = q1_stmt.join(Subject, KnowledgeChunk.subject_id == Subject.id).where(Subject.dept_id == user.dept_id)
        q2_stmt = q2_stmt.join(Subject, Question.subject_id == Subject.id).where(Subject.dept_id == user.dept_id)
        q3_stmt = q3_stmt.join(Subject, Question.subject_id == Subject.id).where(Subject.dept_id == user.dept_id)
        q4_stmt = q4_stmt.join(Subject, QuestionPaper.subject_id == Subject.id).where(Subject.dept_id == user.dept_id)
        q5_stmt = q5_stmt.join(Subject, Question.subject_id == Subject.id).where(Subject.dept_id == user.dept_id)
    else:
        # Admin or fallback HOD with no dept
        pass

    if subject_id:
        q1_stmt = q1_stmt.where(KnowledgeChunk.subject_id == subject_id)
        q2_stmt = q2_stmt.where(Question.subject_id == subject_id)
        q3_stmt = q3_stmt.where(Question.subject_id == subject_id)
        q4_stmt = q4_stmt.where(QuestionPaper.subject_id == subject_id)
        q5_stmt = q5_stmt.where(Question.subject_id == subject_id)

    # 2. Execute Batch Queries
    # Q1
    q1_rows = db.execute(q1_stmt.group_by(KnowledgeChunk.module_number)).all()
    module_chunk_counts = [
        {"module_number": row[0], "chunk_count": row[1]}
        for row in q1_rows
    ]

    # Q2
    q2_rows = db.execute(q2_stmt.group_by(Question.bloom_level)).all()
    bloom_question_counts = [
        {"bloom_level": row[0] or "Unknown", "question_count": row[1]}
        for row in q2_rows
    ]

    # Q3
    q3_rows = db.execute(q3_stmt.group_by(Question.course_outcome)).all()
    co_question_counts = [
        {"course_outcome": row[0] or "Unknown", "question_count": row[1]}
        for row in q3_rows
    ]

    # Q4
    total_papers = db.scalar(q4_stmt) or 0

    # Q5 & Q6: Gap Calculations
    q5_rows = db.execute(q5_stmt.group_by(Question.module_number)).all()
    module_question_counts = {row[0]: row[1] for row in q5_rows if row[0] is not None}
    
    coverage_gaps = []
    for m in range(1, 6):
        cnt = module_question_counts.get(m, 0)
        if cnt < 5:  # threshold is 5 questions per module
            coverage_gaps.append({
                "module_number": m,
                "count": cnt,
                "gap_reason": "No questions created" if cnt == 0 else f"Low question count ({cnt} questions, target is 5)"
            })

    bloom_counts = {row["bloom_level"]: row["question_count"] for row in bloom_question_counts}
    bloom_gaps = []
    target_levels = ["L1", "L2", "L3", "L4"]
    for level in target_levels:
        cnt = bloom_counts.get(level, 0)
        if cnt == 0:
            bloom_gaps.append({
                "bloom_level": level,
                "gap_reason": f"No questions targeting Bloom's taxonomy level {level}"
            })

    return {
        "module_chunk_counts": module_chunk_counts,
        "bloom_question_counts": bloom_question_counts,
        "co_question_counts": co_question_counts,
        "total_papers_semester": total_papers,
        "coverage_gaps": coverage_gaps,
        "bloom_gaps": bloom_gaps,
    }

