from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import PaperStatus, ReviewDecision, Role


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: Role
    dept_id: int | None
    department_name: str | None = None


class SubjectResponse(BaseModel):
    id: int
    code: str
    name: str
    semester: int
    dept_id: int
    department_name: str


class SubjectCreate(BaseModel):
    name: str
    code: str
    department_id: int
    semester: int


class QuestionCreate(BaseModel):
    subject_id: int
    text: str
    marks: int = Field(ge=1, le=30)
    course_outcome: str
    bloom_level: str
    difficulty: str
    module_number: int = Field(ge=1, le=10)
    tags: list[str] = Field(default_factory=list)


class QuestionResponse(QuestionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teacher_id: int
    is_verified: bool
    created_at: datetime


class UploadResponse(BaseModel):
    document_id: int
    extracted_questions: int
    filename: str
    ai_mode: str
    summary: dict | None = None


class GeneratePaperRequest(BaseModel):
    subject_id: int
    title: str
    exam_type: str
    semester: str
    batch: str
    max_marks: int = Field(ge=5, le=200)
    duration_minutes: int = Field(ge=30, le=240)
    exam_date: date | None = None
    teaching_department: str
    prompt: str
    rbt_levels: list[str] = Field(default_factory=list)
    module_numbers: list[int] = Field(default_factory=list)
    difficulty_distribution: dict[str, int] = Field(default_factory=dict)
    co_targets: dict[str, int] = Field(default_factory=dict)
    module_co_map: dict[int, str] | None = None
    module_image_map: dict[int, bool] | None = None
    co_descriptions: dict[str, str] = Field(default_factory=dict)
    difficulty: str = "balanced"
    instructions: str = "Instruction: Answer the following questions"
    manual_question_ids: list[int] = Field(default_factory=list)
    allow_ai_rewrite: bool = False
    creativity: float = Field(default=0.7, ge=0.0, le=1.0)
    use_notes: bool = True
    use_question_bank: bool = True
    use_previous_papers: bool = False
    use_syllabus: bool = True


class PaperQuestionItem(BaseModel):
    id: int
    question_id: int
    order_index: int
    section_label: str
    custom_marks: int | None
    text: str
    course_outcome: str | None = None
    bloom_level: str | None = None
    module_number: int | None = None
    difficulty: str | None = None
    confidence: float | None = None
    source_documents: list[str] = Field(default_factory=list)


class PaperResponse(BaseModel):
    id: int
    subject_id: int
    subject_name: str | None = None
    subject_code: str | None = None
    department_name: str | None = None
    title: str
    exam_type: str
    semester: str
    batch: str
    max_marks: int
    duration_minutes: int
    exam_date: date | None
    teaching_department: str
    status: PaperStatus
    prompt_used: str
    generated_summary: str
    created_at: datetime
    submitted_at: datetime | None
    reviewed_at: datetime | None
    ai_config: dict = Field(default_factory=dict)
    coverage_stats: dict = Field(default_factory=dict)
    questions: list[PaperQuestionItem]


class QuestionBankSummaryResponse(BaseModel):
    total_documents: int
    total_questions: int
    verified_questions: int
    pending_questions: int
    retrieval_ready_questions: int
    by_module: dict[str, int]
    by_rbt: dict[str, int]
    by_co: dict[str, int]
    by_difficulty: dict[str, int]
    recent_documents: list[dict]
    gaps: list[str]


class PaperUpdateRequest(BaseModel):
    title: str | None = None
    prompt: str | None = None
    question_text_overrides: dict[int, str] = Field(default_factory=dict)


class ReviewActionRequest(BaseModel):
    decision: ReviewDecision
    comments: str = Field(min_length=3)


class AdminUserCreate(BaseModel):
    email: str
    full_name: str
    password: str = Field(min_length=8)
    role: Role
    dept_id: int | None = None


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    details: dict
    created_at: datetime


class DashboardResponse(BaseModel):
    total_users: int
    total_subjects: int
    total_questions: int
    total_papers: int
    pending_reviews: int
    approved_papers: int
    ai_model: str
