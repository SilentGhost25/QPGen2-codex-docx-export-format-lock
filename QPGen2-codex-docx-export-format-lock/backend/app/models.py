from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum

from sqlalchemy import JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Role(StrEnum):
    TEACHER = "teacher"
    HOD = "hod"
    ADMIN = "admin"


class PaperStatus(StrEnum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PRINT_READY = "print_ready"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    subjects: Mapped[list["Subject"]] = relationship(back_populates="department")
    users: Mapped[list["User"]] = relationship(back_populates="department")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    semester: Mapped[int] = mapped_column(Integer)
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_marks: Mapped[int] = mapped_column(Integer, default=50)

    department: Mapped["Department"] = relationship(back_populates="subjects")
    teacher_links: Mapped[list["TeacherSubject"]] = relationship(back_populates="subject")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role))
    dept_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    department: Mapped["Department | None"] = relationship(back_populates="users")
    subjects: Mapped[list["TeacherSubject"]] = relationship(back_populates="teacher")


class TeacherSubject(Base):
    __tablename__ = "teacher_subjects"
    __table_args__ = (UniqueConstraint("teacher_id", "subject_id", name="uq_teacher_subject"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))

    teacher: Mapped["User"] = relationship(back_populates="subjects")
    subject: Mapped["Subject"] = relationship(back_populates="teacher_links")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), nullable=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(120))
    storage_path: Mapped[str] = mapped_column(String(500))
    parsed_text: Mapped[str] = mapped_column(Text)
    upload_status: Mapped[str] = mapped_column(String(40), default="processed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_doc_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    marks: Mapped[int] = mapped_column(Integer)
    course_outcome: Mapped[str] = mapped_column(String(20))
    bloom_level: Mapped[str] = mapped_column(String(10))
    difficulty: Mapped[str] = mapped_column(String(20))
    module_number: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding_vector: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class QuestionPaper(Base):
    __tablename__ = "question_papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    exam_type: Mapped[str] = mapped_column(String(50))
    semester: Mapped[str] = mapped_column(String(20))
    batch: Mapped[str] = mapped_column(String(20))
    max_marks: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    teaching_department: Mapped[str] = mapped_column(String(255))
    status: Mapped[PaperStatus] = mapped_column(Enum(PaperStatus), default=PaperStatus.DRAFT)
    prompt_used: Mapped[str] = mapped_column(Text)
    ai_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_summary: Mapped[str] = mapped_column(Text, default="")
    download_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    questions: Mapped[list["PaperQuestion"]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class PaperQuestion(Base):
    __tablename__ = "paper_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("question_papers.id"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    order_index: Mapped[int] = mapped_column(Integer)
    section_label: Mapped[str] = mapped_column(String(20), default="A")
    option_group: Mapped[str | None] = mapped_column(String(20), nullable=True)
    custom_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    question_text_snapshot: Mapped[str] = mapped_column(Text)

    paper: Mapped["QuestionPaper"] = relationship(back_populates="questions")


class PaperReview(Base):
    __tablename__ = "paper_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("question_papers.id"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[ReviewDecision] = mapped_column(Enum(ReviewDecision))
    comments: Mapped[str] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
