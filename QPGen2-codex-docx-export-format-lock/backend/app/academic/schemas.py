"""Pydantic schemas for the Academic Knowledge Intelligence Layer."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from .models import ChunkApprovalStatus, DocumentType, ProcessingStatus


# ---------------------------------------------------------------------------
# Upload / Ingestion
# ---------------------------------------------------------------------------

class AcademicUploadRequest(BaseModel):
    subject_id: int
    document_type: DocumentType = DocumentType.NOTES


class AcademicDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    uploaded_by: int
    file_name: str
    file_type: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    processing_error: str | None = None
    page_count: int | None = None
    total_chunks: int
    # Multimodal summary flags
    has_equations: bool = False
    has_figures: bool = False
    has_tables: bool = False
    equation_count: int = 0
    figure_count: int = 0
    table_count: int = 0
    created_at: datetime


class StructuredContentResponse(BaseModel):
    """Full structured document content (pages + blocks)."""
    model_config = ConfigDict(from_attributes=True)

    document_id: int
    file_name: str
    processing_status: ProcessingStatus
    structured_content: dict | None = None
    has_equations: bool = False
    has_figures: bool = False
    has_tables: bool = False
    equation_count: int = 0
    figure_count: int = 0
    table_count: int = 0


class AcademicDocumentListResponse(BaseModel):
    documents: list[AcademicDocumentResponse]
    total: int


# ---------------------------------------------------------------------------
# Knowledge Chunks
# ---------------------------------------------------------------------------

class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    subject_id: int
    chunk_text: str
    chunk_summary: str | None = None
    chunk_index: int
    token_count: int
    module_number: int | None = None
    syllabus_unit: str | None = None
    topic_name: str | None = None
    bloom_level: str | None = None
    co_mapping: str | None = None
    page_number: int | None = None
    confidence_score: float
    approval_status: ChunkApprovalStatus
    reviewed_by: int | None = None
    review_notes: str | None = None
    created_at: datetime


class ChunkApprovalRequest(BaseModel):
    approval_status: ChunkApprovalStatus
    review_notes: str | None = None


class ChunkEditRequest(BaseModel):
    chunk_text: str | None = None
    module_number: int | None = None
    topic_name: str | None = None
    bloom_level: str | None = None
    co_mapping: str | None = None


class ChunkSearchRequest(BaseModel):
    query: str
    subject_id: int | None = None
    module_number: int | None = None
    document_type: DocumentType | None = None
    limit: int = Field(default=20, ge=1, le=100)


class ChunkSearchResponse(BaseModel):
    chunks: list[KnowledgeChunkResponse]
    total: int
    query: str


# ---------------------------------------------------------------------------
# Subject Syllabus
# ---------------------------------------------------------------------------

class SyllabusModuleItem(BaseModel):
    module: int
    title: str
    topics: list[str]


class SubjectSyllabusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    syllabus_text: str | None = None
    modules_json: list[dict] | None = None
    co_json: dict | None = None
    rbt_rules: dict | None = None
    created_at: datetime


class SyllabusUploadRequest(BaseModel):
    subject_id: int
    syllabus_text: str | None = None
    modules: list[SyllabusModuleItem] | None = None
    co_definitions: dict[str, str] | None = None
    rbt_rules: dict[str, list[str]] | None = None


# ---------------------------------------------------------------------------
# Question Generation Profile
# ---------------------------------------------------------------------------

class GenerationProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    use_notes: bool
    use_question_bank: bool
    use_previous_papers: bool
    use_syllabus: bool
    strict_vtu_mode: bool
    strict_syllabus_mode: bool
    creativity_level: float
    created_at: datetime


class GenerationProfileUpdate(BaseModel):
    use_notes: bool | None = None
    use_question_bank: bool | None = None
    use_previous_papers: bool | None = None
    use_syllabus: bool | None = None
    strict_vtu_mode: bool | None = None
    strict_syllabus_mode: bool | None = None
    creativity_level: float | None = Field(default=None, ge=0.0, le=1.0)


# ---------------------------------------------------------------------------
# Retrieval Source Selection (used during generation)
# ---------------------------------------------------------------------------

class RetrievalSourceSelection(BaseModel):
    """Teacher toggles for choosing generation sources."""
    use_notes: bool = True
    use_question_bank: bool = True
    use_previous_papers: bool = False
    use_syllabus: bool = True


# ---------------------------------------------------------------------------
# Topic Coverage
# ---------------------------------------------------------------------------

class TopicCoverageItem(BaseModel):
    module_number: int
    topic_name: str
    chunk_count: int
    document_count: int
    avg_confidence: float


class TopicCoverageResponse(BaseModel):
    subject_id: int
    total_chunks: int
    total_documents: int
    coverage: list[TopicCoverageItem]
    gaps: list[str]


# ---------------------------------------------------------------------------
# Retrieval-Constrained Generation (Phase 6)
# ---------------------------------------------------------------------------

class RAGGenerationRequest(BaseModel):
    """Request for retrieval-constrained question generation."""
    subject_id: int
    num_questions: int = Field(default=10, ge=1, le=50)
    marks_distribution: dict[int, int] | None = None  # {2: 5, 5: 3, 10: 2}
    bloom_levels: list[str] | None = None  # ["L1", "L2", "L3"]
    co_targets: list[str] | None = None  # ["CO1", "CO2"]
    question_types: list[str] | None = None  # ["theory", "numerical"]
    module_filter: int | None = Field(default=None, ge=1, le=5)
    additional_instructions: str | None = None
    creativity_override: float | None = Field(default=None, ge=0.0, le=1.0)
    existing_question_texts: list[str] | None = None  # For dedup


class RAGGeneratedQuestionResponse(BaseModel):
    """A single generated question with source traceability."""
    text: str
    marks: int
    bloom_level: str
    co_mapping: str
    module_number: int | None = None
    question_type: str
    topic_name: str | None = None
    source_chunk_ids: list[int] = []
    source_documents: list[str] = []
    confidence: float
    is_valid: bool
    validation_errors: list[str] = []
    validation_warnings: list[str] = []


class RAGGenerationResponse(BaseModel):
    """Full response from retrieval-constrained generation."""
    model_config = ConfigDict(protected_namespaces=())

    questions: list[RAGGeneratedQuestionResponse]
    retrieval_summary: dict
    validation_summary: dict
    generation_time: float
    model_used: str
    creativity_level: float
    temperature: float


# ---------------------------------------------------------------------------
# Analytics Dashboard (Phase 6)
# ---------------------------------------------------------------------------

class ModuleChunkCount(BaseModel):
    module_number: int | None = None
    chunk_count: int

class BloomQuestionCount(BaseModel):
    bloom_level: str
    question_count: int

class COQuestionCount(BaseModel):
    course_outcome: str
    question_count: int

class CoverageGap(BaseModel):
    module_number: int
    count: int
    gap_reason: str

class BloomGap(BaseModel):
    bloom_level: str
    gap_reason: str

class AnalyticsDashboardResponse(BaseModel):
    module_chunk_counts: list[ModuleChunkCount]
    bloom_question_counts: list[BloomQuestionCount]
    co_question_counts: list[COQuestionCount]
    total_papers_semester: int
    coverage_gaps: list[CoverageGap]
    bloom_gaps: list[BloomGap]
