from __future__ import annotations
import logging
import random

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app")

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .auth import create_auth_tokens, decode_token, get_current_user, require_roles
from .config import settings
from .database import Base, engine, get_db, SessionLocal
from .models import (
    AuditLog,
    Department,
    PaperStatus,
    Question,
    QuestionPaper,
    Role,
    Subject,
    TeacherSubject,
    User,
)
from .schemas import (
    AdminUserCreate,
    AuditLogResponse,
    DashboardResponse,
    GeneratePaperRequest,
    LoginRequest,
    PaperResponse,
    PaperUpdateRequest,
    QuestionCreate,
    QuestionBankSummaryResponse,
    QuestionResponse,
    RefreshRequest,
    ReviewActionRequest,
    SubjectCreate,
    SubjectResponse,
    TokenResponse,
    UploadResponse,
    UserSummary,
)
from .services import (
    authenticate_user,
    create_admin_user,
    create_question,
    dashboard_stats,
    delete_paper,
    delete_question,
    ensure_paper_access,
    export_paper_docx,
    generate_paper,
    get_paper_or_404,
    list_papers_for_user,
    list_questions_for_user,
    parse_uploaded_document,
    review_paper,
    seed_demo_data,
    serialize_paper,
    submit_paper,
    update_question,
    update_paper,
)

from .ai_service import (
    OllamaClient,
    process_question_bank,
    select_questions_for_paper,
    summarize_question_bank,
)
from .generator import PaperConfig, build_question_blueprint, generate_question_paper

# Import academic models so they are registered with Base.metadata
from .academic.models import (  # noqa: F401
    AcademicDocument,
    KnowledgeChunk,
    SubjectSyllabus,
    QuestionGenerationProfile,
)
from .academic.routes import router as academic_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_demo_data(session)
    
    if settings.prewarm_embeddings_on_startup:
        try:
            from .academic.embeddings import _get_model

            logger.info("Pre-warming embedding model...")
            _get_model()
            logger.info("Embedding model pre-warmed and ready")
        except Exception as e:
            logger.warning("Could not pre-warm embedding model: %s", e)
    
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.include_router(academic_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _build_coverage_stats(
    questions: list[Question],
    blueprint: list[dict[str, int | str]],
    requested_modules: list[int],
    requested_rbt: dict[str, int],
    requested_co: dict[str, int],
) -> dict:
    slot_marks = [int(slot["marks"]) for slot in blueprint[: len(questions)]]
    total = sum(slot_marks) or 1
    by_module = {str(module): 0 for module in (requested_modules or [1, 2, 3, 4, 5])}
    by_rbt = {f"L{level}": 0 for level in range(1, 7)}
    by_co = {f"CO{level}": 0 for level in range(1, 7)}

    for question, marks in zip(questions, slot_marks):
        by_module[str(question.module_number)] = (
            by_module.get(str(question.module_number), 0) + marks
        )
        by_rbt[question.bloom_level] = by_rbt.get(question.bloom_level, 0) + marks
        by_co[question.course_outcome.upper()] = (
            by_co.get(question.course_outcome.upper(), 0) + marks
        )

    return {
        "question_count": len(questions),
        "by_module": by_module,
        "by_rbt": by_rbt,
        "by_co": by_co,
        "requested": {
            "modules": requested_modules,
            "rbt": requested_rbt,
            "co": requested_co,
        },
        "percentages": {
            "co": {
                key: round((value / total) * 100)
                for key, value in by_co.items()
                if key in requested_co or value
            },
            "modules": {
                key: round((value / total) * 100)
                for key, value in by_module.items()
                if int(key) in requested_modules or value
            },
        },
    }


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": settings.ollama_model}


@app.post("/api/v1/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> dict[str, str]:
    return authenticate_user(db, payload.email, payload.password)


@app.post("/api/v1/auth/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    decoded = decode_token(payload.refresh_token)
    if decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    user = db.get(User, int(decoded["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable"
        )
    return create_auth_tokens(user)


@app.get("/api/v1/users/me", response_model=UserSummary)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    dept_name = None
    if user.dept_id:
        department = db.get(Department, user.dept_id)
        dept_name = department.name if department else None
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "dept_id": user.dept_id,
        "department_name": dept_name,
    }


@app.get("/api/v1/departments")
def list_departments(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    departments = db.scalars(select(Department).order_by(Department.name)).all()
    return [{"id": d.id, "name": d.name, "code": d.code} for d in departments]


@app.get("/api/v1/subjects", response_model=list[SubjectResponse])
def subjects(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    stmt = select(Subject).options(selectinload(Subject.department))
    if user.role != Role.ADMIN and user.dept_id is not None:
        stmt = stmt.where(Subject.dept_id == user.dept_id)
    return [
        {
            "id": subject.id,
            "code": subject.code,
            "name": subject.name,
            "semester": subject.semester,
            "dept_id": subject.dept_id,
            "department_name": subject.department.name,
        }
        for subject in db.scalars(stmt.order_by(Subject.semester, Subject.name))
    ]


@app.post("/api/v1/subjects", response_model=SubjectResponse)
def create_subject(
    payload: SubjectCreate,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    dept = db.get(Department, payload.department_id)
    if not dept:
        raise HTTPException(status_code=404, detail="Department not found")
    subject = Subject(
        name=payload.name,
        code=payload.code,
        dept_id=payload.department_id,
        semester=payload.semester,
    )
    db.add(subject)
    db.flush() # flush to get subject.id before commit
    
    # Automatically assign the creator to the subject so they can upload immediately
    teacher_subject = TeacherSubject(
        teacher_id=user.id,
        subject_id=subject.id
    )
    db.add(teacher_subject)
    
    db.commit()
    db.refresh(subject)
    return {
        "id": subject.id,
        "code": subject.code,
        "name": subject.name,
        "semester": subject.semester,
        "dept_id": subject.dept_id,
        "department_name": dept.name,
    }


@app.post("/api/v1/questions", response_model=QuestionResponse)
def add_question(
    payload: QuestionCreate,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> QuestionResponse:
    return create_question(db, user, payload.model_dump())


@app.post("/api/v1/questions/upload", response_model=UploadResponse)
def upload_question_bank(
    subject_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    document, questions, ai_mode = parse_uploaded_document(db, user, subject_id, file)
    return {
        "document_id": document.id,
        "extracted_questions": len(questions),
        "filename": document.filename,
        "ai_mode": ai_mode,
    }


@app.post("/api/v1/ai/process-question-bank")
async def ai_process_question_bank(
    subject_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    result = await process_question_bank(file, subject_id, user.id, db)
    return {
        "success": result.success,
        "document_id": result.document_id,
        "filename": result.filename,
        "total_extracted": result.total_extracted,
        "auto_approved": result.auto_approved,
        "processing_time": round(result.processing_time, 2),
        "ai_model": result.ai_model,
        "ai_mode": result.ai_mode,
        "summary": result.summary,
        "error": result.error,
    }


@app.get(
    "/api/v1/ai/question-bank-summary",
    response_model=QuestionBankSummaryResponse,
)
def ai_question_bank_summary(
    subject_id: int | None = None,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    subject_ids: list[int] | None = None
    teacher_id: int | None = user.id if user.role == Role.TEACHER else None

    if subject_id is not None:
        subject = db.get(Subject, subject_id)
        if subject is None:
            raise HTTPException(status_code=404, detail="Subject not found")
        if user.role != Role.ADMIN and user.dept_id != subject.dept_id:
            raise HTTPException(status_code=403, detail="Department access denied")
        if user.role == Role.TEACHER:
            assigned = db.scalar(
                select(Subject.id)
                .join_from(Subject, TeacherSubject, Subject.id == TeacherSubject.subject_id)
                .where(TeacherSubject.teacher_id == user.id, Subject.id == subject_id)
            )
            if assigned is None:
                raise HTTPException(
                    status_code=403,
                    detail="Teacher is not assigned to this subject",
                )
        subject_ids = [subject_id]
    elif user.role == Role.HOD and user.dept_id is not None:
        subject_ids = list(
            db.scalars(select(Subject.id).where(Subject.dept_id == user.dept_id))
        )

    summary = summarize_question_bank(db, subject_ids=subject_ids, teacher_id=teacher_id)
    return {
        "total_documents": summary.total_documents,
        "total_questions": summary.total_questions,
        "verified_questions": summary.verified_questions,
        "pending_questions": summary.pending_questions,
        "retrieval_ready_questions": summary.retrieval_ready_questions,
        "by_module": summary.by_module,
        "by_rbt": summary.by_rbt,
        "by_co": summary.by_co,
        "by_difficulty": summary.by_difficulty,
        "recent_documents": summary.recent_documents,
        "gaps": summary.gaps,
    }


@app.post("/api/v1/ai/generate-paper")
async def ai_generate_paper(
    payload: GeneratePaperRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    subject = db.get(Subject, payload.subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    rbt_dist = payload.model_dump().get(
        "rbt_levels", ["L1", "L2", "L3", "L4", "L5", "L6"]
    )
    rbt_dict = {rbt: 100 // len(rbt_dist) for rbt in rbt_dist}

    co_targets = payload.model_dump().get("co_targets", {})
    if not co_targets:
        co_targets = {f"CO{i}": 100 // 5 for i in range(1, 6)}

    modules = payload.model_dump().get("module_numbers", [1, 2, 3, 4, 5])
    difficulty = payload.model_dump().get("difficulty", "medium")
    module_co_map = payload.module_co_map or {}
    module_image_map = payload.module_image_map or {}
    blueprint = build_question_blueprint(payload.max_marks, module_co_map=module_co_map, module_image_map=module_image_map)
    manual_question_ids = list(dict.fromkeys(payload.manual_question_ids))

    if manual_question_ids:
        question_rows = list(
            db.scalars(
                select(Question).where(
                    Question.subject_id == payload.subject_id,
                    Question.id.in_(manual_question_ids),
                )
            )
        )
        question_by_id = {question.id: question for question in question_rows}
        questions = [
            question_by_id[question_id]
            for question_id in manual_question_ids
            if question_id in question_by_id
        ]
        coverage_stats = _build_coverage_stats(
            questions,
            blueprint,
            modules,
            rbt_dict,
            co_targets,
        )
    else:
        use_rag = any(
            (
                payload.use_notes,
                payload.use_question_bank,
                payload.use_previous_papers,
                payload.use_syllabus,
            )
        )
        
        if use_rag:
            from .academic.generation import generate_questions_from_retrieval
            from .academic.retrieval import RetrievalError

            marks_dist = {}
            for slot in blueprint:
                marks_dist[slot["marks"]] = marks_dist.get(slot["marks"], 0) + 1
            
            teacher_id = user.id if user.role == Role.TEACHER else None
            try:
                result = generate_questions_from_retrieval(
                    db=db,
                    subject_id=payload.subject_id,
                    num_questions=len(blueprint),
                    blueprint=blueprint,
                    bloom_levels=payload.model_dump().get("rbt_levels", []),
                    co_targets=list(co_targets.keys()),
                    module_filter=modules[0] if len(modules) == 1 else None,
                    additional_instructions=payload.prompt,
                    creativity_override=payload.creativity,
                    use_notes=payload.use_notes,
                    use_question_bank=payload.use_question_bank,
                    use_previous_papers=payload.use_previous_papers,
                    use_syllabus=payload.use_syllabus,
                    teacher_id=teacher_id,
                )
            except RetrievalError as e:
                logger.exception("Retrieval failed during paper generation")
                raise HTTPException(
                    status_code=400,
                    detail=str(e),
                )

            valid_generated_questions = [
                question
                for question in result.questions
                if question.text
            ]

            questions = []
            if len(valid_generated_questions) >= len(blueprint):
                from .academic.sanitizer import sanitize_question_output
                for gq in valid_generated_questions[: len(blueprint)]:
                    cleaned_text = sanitize_question_output(gq.text)
                    q_row = Question(
                        subject_id=payload.subject_id,
                        teacher_id=user.id,
                        text=cleaned_text,
                        marks=gq.marks,
                        course_outcome=gq.co_mapping,
                        bloom_level=gq.bloom_level,
                        difficulty="medium",
                        module_number=gq.module_number or 1,
                        tags=["rag-generated"],
                        is_verified=gq.confidence >= 0.8,
                    )
                    db.add(q_row)
                    db.flush()
                    q_row._confidence = gq.confidence
                    q_row._source_documents = gq.source_documents
                    questions.append(q_row)

            if len(questions) < len(blueprint):
                logger.error(
                    "RAG generation failed to produce enough valid questions grounded in the retrieval context (needed %d, got %d)",
                    len(blueprint),
                    len(questions),
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"RAG generation was unable to generate enough valid questions grounded in the context (needed {len(blueprint)}, got {len(questions)}). Check that your uploaded files contain relevant concepts, or try modifying the generation settings.",
                )
            else:
                coverage_stats = _build_coverage_stats(
                    questions,
                    blueprint,
                    modules,
                    rbt_dict,
                    co_targets,
                )
        else:
            selection = await select_questions_for_paper(
                db,
                payload.subject_id,
                payload.max_marks,
                modules,
                rbt_dict,
                co_targets,
                difficulty,
                payload.prompt,
            )
            questions = selection.questions
            coverage_stats = selection.coverage_stats


    if not questions:
        raise HTTPException(
            status_code=400,
            detail="No suitable questions found for the selected criteria",
        )

    if len(questions) < len(blueprint):
        logger.warning(
            "Only %d questions available for a %d-slot blueprint; padding with reused questions",
            len(questions),
            len(blueprint),
        )
        padded_questions = list(questions)
        source_questions = list(questions)
        while len(padded_questions) < len(blueprint):
            padded_questions.append(source_questions[len(padded_questions) % len(source_questions)])
        questions = padded_questions

    dept_name = subject.department.name if subject.department else "CSE"

    config = PaperConfig(
        department=dept_name,
        subject=subject.name,
        subject_code=subject.code,
        semester=payload.semester,
        max_marks=payload.max_marks,
        duration=f"{payload.duration_minutes} Minutes",
        date=payload.exam_date.strftime("%d-%m-%Y")
        if payload.exam_date
        else "To be announced",
        batch=payload.batch,
        teaching_department=payload.teaching_department,
        exam_type=payload.exam_type,
        modules=modules,
        rbt_levels=rbt_dist,
        co_targets=list(co_targets.keys()),
        instructions=payload.instructions,
        co_descriptions=payload.co_descriptions,
        co_percentages=coverage_stats.get("percentages", {}).get("co", {}),
        module_percentages=coverage_stats.get("percentages", {}).get("modules", {}),
        template_note=(
            "Answer any FIVE full questions, choosing at least ONE question from each MODULE"
            if payload.max_marks >= 100
            else None
        ),
        template_family="semester-end" if payload.max_marks >= 100 else "internal-assessment",
    )

    questions_data = [
        {
            "id": q.id,
            "text": q.text,
            "marks": blueprint[index]["marks"],
            "course_outcome": q.course_outcome,
            "bloom_level": q.bloom_level,
            "difficulty": q.difficulty,
            "module_number": q.module_number,
            "confidence": getattr(q, "_confidence", None),
            "source_documents": getattr(q, "_source_documents", []),
        }
        for index, q in enumerate(questions[: len(blueprint)])
    ]

    client = OllamaClient()
    if payload.allow_ai_rewrite and await client.is_available():
        rewritten = await client.rephrase_questions(
            questions_data,
            subject.name or "Subject",
            subject.code or "N/A",
            payload.semester,
            payload.exam_type,
            payload.prompt,
        )
        if rewritten:
            questions_data = rewritten

    if not manual_question_ids:
        random.shuffle(questions_data)

    questions_data = [
        {
            "text": item["text"],
            "marks": item["marks"],
            "course_outcome": item.get("course_outcome", ""),
            "bloom_level": item.get("bloom_level", ""),
            "module_number": item.get("module_number"),
            "confidence": item.get("confidence"),
            "source_documents": item.get("source_documents", []),
        }
        for item in questions_data
    ]

    output_path = Path(settings.storage_path) / "papers"
    docx_path = generate_question_paper(config, questions_data, output_path)

    paper = QuestionPaper(
        subject_id=payload.subject_id,
        teacher_id=user.id,
        title=payload.title,
        exam_type=payload.exam_type,
        semester=payload.semester,
        batch=payload.batch,
        max_marks=payload.max_marks,
        duration_minutes=payload.duration_minutes,
        exam_date=payload.exam_date,
        teaching_department=payload.teaching_department,
        prompt_used=payload.prompt,
        generated_summary=(
            f"{'Manually selected' if manual_question_ids else 'AI selected'} "
            f"{len(questions_data)} slot-aligned questions for {subject.code} across "
            f"{len({question.module_number for question in questions[: len(blueprint)]})} modules."
        ),
        ai_config_json={
            "rbt_levels": rbt_dist,
            "module_numbers": modules,
            "co_targets": co_targets,
            "co_descriptions": payload.co_descriptions,
            "difficulty": difficulty,
            "manual_question_ids": manual_question_ids,
            "instructions": payload.instructions,
            "template_note": (
                "Answer any FIVE full questions, choosing at least ONE question from each MODULE"
                if payload.max_marks >= 100
                else None
            ),
            "coverage_stats": coverage_stats,
        },
        status=PaperStatus.DRAFT,
        download_path=str(docx_path),
    )
    db.add(paper)
    db.flush()

    from .models import PaperQuestion

    for idx, q in enumerate(questions[: len(blueprint)], 1):
        slot = blueprint[idx - 1]
        db.add(
            PaperQuestion(
                paper_id=paper.id,
                question_id=q.id,
                order_index=idx,
                section_label=slot["label"],
                option_group=f"CHOICE-{((slot['question_number'] - 1) // 2) + 1}",
                custom_marks=slot["marks"],
                question_text_snapshot=q.text,
            )
        )

    db.commit()

    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper.id)
    )
    return serialize_paper(db, paper)


@app.get("/api/v1/questions", response_model=list[QuestionResponse])
def list_questions(
    search: str | None = None,
    subject_id: int | None = None,
    bloom_level: str | None = None,
    difficulty: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionResponse]:
    return list_questions_for_user(
        db, user, search, subject_id, bloom_level, difficulty
    )


@app.put("/api/v1/questions/{question_id}", response_model=QuestionResponse)
def edit_question(
    question_id: int,
    payload: QuestionCreate,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> QuestionResponse:
    return update_question(db, user, question_id, payload.model_dump())


@app.delete("/api/v1/questions/{question_id}", status_code=200, response_class=Response)
def remove_question(
    question_id: int,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    delete_question(db, user, question_id)


@app.post("/api/v1/papers/generate", response_model=PaperResponse)
def create_paper(
    payload: GeneratePaperRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    paper = generate_paper(db, user, payload.model_dump())
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper.id)
    )
    return serialize_paper(db, paper)


@app.get("/api/v1/papers", response_model=list[PaperResponse])
def list_papers(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    return [serialize_paper(db, paper) for paper in list_papers_for_user(db, user)]


@app.get("/api/v1/papers/{paper_id}/preview", response_model=PaperResponse)
def preview_paper(
    paper_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    ensure_paper_access(db, user, paper)
    return serialize_paper(db, paper)


@app.put("/api/v1/papers/{paper_id}", response_model=PaperResponse)
def edit_paper(
    paper_id: int,
    payload: PaperUpdateRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    paper = update_paper(
        db, user, paper, payload.title, payload.prompt, payload.question_text_overrides
    )
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper.id)
    )
    return serialize_paper(db, paper)


@app.post("/api/v1/papers/{paper_id}/submit", response_model=PaperResponse)
def submit_paper_for_review(
    paper_id: int,
    user: User = Depends(require_roles(Role.TEACHER)),
    db: Session = Depends(get_db),
) -> dict:
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    paper = submit_paper(db, user, paper)
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper.id)
    )
    return serialize_paper(db, paper)


@app.get("/api/v1/reviews/pending", response_model=list[PaperResponse])
def pending_reviews(
    user: User = Depends(require_roles(Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = (
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.status == PaperStatus.PENDING_REVIEW)
    )
    if user.role == Role.HOD and user.dept_id is not None:
        subject_ids = select(Subject.id).where(Subject.dept_id == user.dept_id)
        stmt = stmt.where(QuestionPaper.subject_id.in_(subject_ids))
    return [
        serialize_paper(db, paper)
        for paper in db.scalars(stmt.order_by(QuestionPaper.submitted_at.desc()))
    ]


@app.post("/api/v1/reviews/{paper_id}/action", response_model=PaperResponse)
def take_review_action(
    paper_id: int,
    payload: ReviewActionRequest,
    user: User = Depends(require_roles(Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    paper = review_paper(db, user, paper, payload.decision, payload.comments)
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper.id)
    )
    return serialize_paper(db, paper)


@app.get("/api/v1/papers/{paper_id}/download")
def download_paper(
    paper_id: int,
    user: User = Depends(require_roles(Role.HOD, Role.ADMIN, Role.TEACHER)),
    db: Session = Depends(get_db),
) -> FileResponse:
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )

    path = export_paper_docx(db, user, paper)

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=path.name,
    )


@app.delete("/api/v1/papers/{paper_id}", status_code=200, response_class=Response)
def remove_paper(
    paper_id: int,
    user: User = Depends(require_roles(Role.TEACHER, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> None:
    paper = db.scalar(
        select(QuestionPaper)
        .options(selectinload(QuestionPaper.questions))
        .where(QuestionPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Paper not found"
        )
    delete_paper(db, user, paper)


@app.post("/api/v1/admin/users", response_model=UserSummary)
def create_user(
    payload: AdminUserCreate,
    user: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    created = create_admin_user(db, user, payload.model_dump())
    dept_name = None
    if created.dept_id:
        department = db.get(Department, created.dept_id)
        dept_name = department.name if department else None
    return {
        "id": created.id,
        "email": created.email,
        "full_name": created.full_name,
        "role": created.role,
        "dept_id": created.dept_id,
        "department_name": dept_name,
    }


@app.get("/api/v1/admin/audit-logs", response_model=list[AuditLogResponse])
def audit_logs(
    _: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    return list(
        db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(100))
    )


@app.get("/api/v1/admin/dashboard", response_model=DashboardResponse)
def admin_dashboard(
    _: User = Depends(require_roles(Role.ADMIN)),
    db: Session = Depends(get_db),
) -> dict:
    return dashboard_stats(db)
