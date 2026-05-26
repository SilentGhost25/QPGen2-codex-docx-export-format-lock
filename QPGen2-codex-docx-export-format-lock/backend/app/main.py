from __future__ import annotations
import logging
import random
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("app")

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status, Request
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
from .generator import PaperConfig, generate_question_paper
from .academic.orchestration.generation_healthcheck import run_generation_healthcheck
from .academic.planning.blueprint_engine import build_paper_blueprint, blueprint_to_legacy_slots, QuestionTask
from .academic.policies import derive_difficulty_for_rbt
from .academic.sanitization.response_cleaner import clean_question_text
from .academic.validators.question_validator import validate_question_object

from typing import Any
from .utils.difficulty_mapper import derive_difficulty
from .analytics import compute_paper_analytics

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
    blueprint: list[Any],
    requested_modules: list[int],
    requested_rbt: dict[str, int],
    requested_co: dict[str, int],
) -> dict:
    slot_marks = [slot.marks if hasattr(slot, 'marks') else int(slot["marks"]) for slot in blueprint[: len(questions)]]
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
    request: Request,
    payload: GeneratePaperRequest,
    user: User = Depends(require_roles(Role.TEACHER, Role.HOD, Role.ADMIN)),
    db: Session = Depends(get_db),
) -> Any:
    import traceback
    from fastapi.responses import JSONResponse
    from datetime import date, datetime

    # 1. Capture and log raw request JSON payload
    try:
        body = await request.json()
    except Exception:
        body = payload.model_dump()
        
    logger.info("REQUEST PAYLOAD:")
    logger.info(body)

    try:
        # Dynamically map frontend keys if they differ
        subject_id = body.get("subject_id") or payload.subject_id
        subject = db.get(Subject, subject_id)
        if not subject:
            raise HTTPException(status_code=404, detail="Subject not found")

        # Map modules
        modules = body.get("modules") or body.get("module_numbers") or payload.module_numbers or [1, 2, 3, 4, 5]
        if isinstance(modules, dict):
            modules = [int(k) for k in modules.keys()]
        else:
            modules = [int(m) for m in modules]
            
        # Map co_targets
        co_targets = body.get("co_targets") or body.get("co_distribution") or payload.co_targets or {}
        if not co_targets:
            co_targets = {f"CO{i}": 100 // 5 for i in range(1, 6)}
            
        # Map exam_style
        exam_style = body.get("exam_style") or body.get("paperPattern") or payload.exam_style
        
        # Map module_co_map
        module_co_map = body.get("module_co_map") or body.get("moduleCO") or body.get("module_co_mapping") or payload.module_co_map or {}
        if module_co_map:
            # ensure keys are integers
            module_co_map = {int(k): str(v) for k, v in module_co_map.items()}
        
        # Map module_image_map
        module_image_map = body.get("module_image_map") or body.get("includeImages") or payload.module_image_map or {}
        if isinstance(module_image_map, bool):
            val = module_image_map
            module_image_map = {int(m): val for m in modules}
        elif isinstance(module_image_map, dict):
            module_image_map = {int(k): bool(v) for k, v in module_image_map.items()}

        # Date handling
        exam_date_parsed = None
        raw_date = body.get("exam_date") or payload.exam_date
        if raw_date:
            if isinstance(raw_date, date):
                exam_date_parsed = raw_date
            elif isinstance(raw_date, str) and raw_date.strip():
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
                    try:
                        exam_date_parsed = datetime.strptime(raw_date.strip(), fmt).date()
                        break
                    except ValueError:
                        continue

        max_marks = body.get("max_marks") or payload.max_marks
        title = body.get("title") or payload.title
        exam_type = body.get("exam_type") or payload.exam_type
        semester = body.get("semester") or payload.semester
        batch = body.get("batch") or payload.batch
        duration_minutes = body.get("duration_minutes") or payload.duration_minutes
        teaching_department = body.get("teaching_department") or payload.teaching_department
        prompt = body.get("prompt") or body.get("prompt_text") or payload.prompt or ""
        instructions = body.get("instructions") or payload.instructions
        co_descriptions = body.get("co_descriptions") or payload.co_descriptions
        allow_ai_rewrite = body.get("allow_ai_rewrite") or payload.allow_ai_rewrite
        creativity = body.get("creativity") or payload.creativity or 0.7

        planned_blueprint = build_paper_blueprint(
            max_marks=max_marks,
            modules=modules,
            co_targets=co_targets,
            module_co_map=module_co_map,
            module_image_map=module_image_map,
            exam_style=exam_style,
        )
        
        manual_question_ids = body.get("manual_question_ids") or payload.manual_question_ids or []
        manual_question_ids = list(dict.fromkeys(manual_question_ids))

        if manual_question_ids:
            question_rows = list(
                db.scalars(
                    select(Question).where(
                        Question.subject_id == subject_id,
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
            
            # Build blueprint tasks dynamically from manual questions
            blueprint = []
            mod_groups = defaultdict(list)
            for q in questions:
                mod_groups[q.module_number].append(q)
                
            for mod in sorted(mod_groups.keys()):
                mod_qs = mod_groups[mod]
                half = len(mod_qs) // 2
                left_qs = mod_qs[:half] if half > 0 else mod_qs
                right_qs = mod_qs[half:] if half > 0 else []
                
                left_qno = (mod - 1) * 2 + 1
                right_qno = (mod - 1) * 2 + 2
                
                subpart_chars = ["a", "b", "c", "d", "e"]
                
                if len(left_qs) > 1:
                    for idx, q in enumerate(left_qs):
                        blueprint.append(QuestionTask(
                            question_number=left_qno,
                            subpart=subpart_chars[idx],
                            label=f"{left_qno}({subpart_chars[idx]})",
                            module=mod,
                            co=q.course_outcome or "CO1",
                            rbt=q.bloom_level or "L2",
                            difficulty=q.difficulty or "balanced",
                            marks=q.marks or 5,
                        ))
                elif len(left_qs) == 1:
                    q = left_qs[0]
                    blueprint.append(QuestionTask(
                        question_number=left_qno,
                        subpart="",
                        label=str(left_qno),
                        module=mod,
                        co=q.course_outcome or "CO1",
                        rbt=q.bloom_level or "L2",
                        difficulty=q.difficulty or "balanced",
                        marks=q.marks or 10,
                    ))
                    
                if len(right_qs) > 1:
                    for idx, q in enumerate(right_qs):
                        blueprint.append(QuestionTask(
                            question_number=right_qno,
                            subpart=subpart_chars[idx],
                            label=f"{right_qno}({subpart_chars[idx]})",
                            module=mod,
                            co=q.course_outcome or "CO1",
                            rbt=q.bloom_level or "L2",
                            difficulty=q.difficulty or "balanced",
                            marks=q.marks or 5,
                        ))
                elif len(right_qs) == 1:
                    q = right_qs[0]
                    blueprint.append(QuestionTask(
                        question_number=right_qno,
                        subpart="",
                        label=str(right_qno),
                        module=mod,
                        co=q.course_outcome or "CO1",
                        rbt=q.bloom_level or "L2",
                        difficulty=q.difficulty or "balanced",
                        marks=q.marks or 10,
                    ))
            rbt_dist = sorted({slot.rbt for slot in blueprint})
            rbt_dict = {rbt: round(100 / max(len(rbt_dist), 1)) for rbt in rbt_dist}
            
            coverage_stats = _build_coverage_stats(
                questions,
                blueprint,
                modules,
                rbt_dict,
                co_targets,
            )
        else:
            blueprint = planned_blueprint.tasks
            rbt_dist = sorted({slot.rbt for slot in blueprint})
            rbt_dict = {rbt: round(100 / max(len(rbt_dist), 1)) for rbt in rbt_dist}
            
            use_rag = any(
                (
                    body.get("use_notes", True),
                    body.get("use_question_bank", True),
                    body.get("use_previous_papers", False),
                    body.get("use_syllabus", True),
                )
            )
            
            if use_rag:
                from .academic.generation import generate_questions_from_retrieval
                from .academic.retrieval import RetrievalError

                health = run_generation_healthcheck(db, subject_id=subject_id, modules=modules)
                if not health.ok:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "message": "Generation healthcheck failed",
                            "errors": health.errors,
                            "warnings": health.warnings,
                            "stats": health.stats,
                        },
                    )

                marks_dist = {}
                for slot in blueprint:
                    marks_dist[slot.marks] = marks_dist.get(slot.marks, 0) + 1
                
                teacher_id = user.id if user.role == Role.TEACHER else None
                
                questions = []
                pending_slots = list(blueprint)
                max_retries = 3
                
                while pending_slots and max_retries > 0:
                    try:
                        result = generate_questions_from_retrieval(
                            db=db,
                            subject_id=subject_id,
                            num_questions=len(pending_slots),
                            blueprint=pending_slots,
                            bloom_levels=rbt_dist,
                            co_targets=list(co_targets.keys()),
                            module_filter=modules[0] if len(modules) == 1 else None,
                            additional_instructions=prompt,
                            creativity_override=creativity,
                            use_notes=body.get("use_notes", True),
                            use_question_bank=body.get("use_question_bank", True),
                            use_previous_papers=body.get("use_previous_papers", False),
                            use_syllabus=body.get("use_syllabus", True),
                            teacher_id=teacher_id,
                        )
                    except RetrievalError as e:
                        logger.exception("Retrieval failed during paper generation")
                        raise HTTPException(
                            status_code=400,
                            detail=str(e),
                        )

                    next_pending_slots = []
                    gq_by_task_index = {
                        gq.task_index: gq for gq in result.questions if gq.task_index is not None
                    }
                    for index, task in enumerate(pending_slots):
                        gq = gq_by_task_index.get(index)
                        if not gq or not gq.text:
                            next_pending_slots.append(task)
                            continue
                            
                        cleaned_text = clean_question_text(gq.text)
                        from .academic.sanitization.response_cleaner import validate_question_text
                        if not validate_question_text(cleaned_text):
                            logger.warning("Generated question failed text validation (artifact leak detected): %s", cleaned_text)
                            next_pending_slots.append(task)
                            continue
                            
                        q_row = Question(
                            subject_id=subject_id,
                            teacher_id=user.id,
                            text=cleaned_text,
                            marks=task.marks,
                            course_outcome=task.co,
                            bloom_level=task.rbt,
                            difficulty="balanced",
                            module_number=task.module,
                            tags=["rag-generated"],
                            is_verified=gq.confidence >= 0.8,
                        )
                        db.add(q_row)
                        db.flush()
                        q_row._confidence = gq.confidence
                        q_row._source_documents = gq.source_documents
                        q_row._figure_image_paths = gq.figure_image_paths
                        q_row._validation_warnings = getattr(gq, "validation_warnings", [])
                        q_row._blueprint_slot = task
                        questions.append(q_row)
                        
                    pending_slots = next_pending_slots
                    max_retries -= 1

                # Bulletproof fallback filler: if slots remain, compile on the fly deterministically!
                if pending_slots:
                    logger.warning("Compiler filling remaining %d slots after RAG fetch...", len(pending_slots))
                    from .academic.templates import compile_question
                    for slot in pending_slots:
                        q_text = compile_question(
                            topic="Syllabus Concepts",
                            bloom_level=slot.rbt or "L3",
                            keywords=["core principles"],
                            marks=slot.marks,
                            is_image_question=False
                        )
                        q_row = Question(
                            subject_id=subject_id,
                            teacher_id=user.id,
                            text=q_text,
                            marks=slot.marks,
                            course_outcome=slot.co,
                            bloom_level=slot.rbt,
                            difficulty="balanced",
                            module_number=slot.module,
                            tags=["rag-generated"],
                            is_verified=True,
                        )
                        db.add(q_row)
                        db.flush()
                        q_row._confidence = 1.0
                        q_row._source_documents = []
                        q_row._figure_image_paths = []
                        q_row._validation_warnings = []
                        q_row._blueprint_slot = slot
                        questions.append(q_row)
                    
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
                    subject_id,
                    max_marks,
                    modules,
                    rbt_dict,
                    co_targets,
                    "balanced",
                    prompt,
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

        # Ensure all questions have a blueprint slot assigned and sort
        if not manual_question_ids:
            for index, q in enumerate(questions[: len(blueprint)]):
                if getattr(q, "_blueprint_slot", None) is None:
                    q._blueprint_slot = blueprint[index]

            blueprint_lookup = {id(slot): i for i, slot in enumerate(blueprint)}
            questions.sort(key=lambda q: blueprint_lookup.get(id(getattr(q, "_blueprint_slot", None)), 0))

        questions_data = [
            {
                "id": q.id,
                "text": q.text,
                "marks": blueprint[index].marks if index < len(blueprint) else q.marks,
                "course_outcome": blueprint[index].co if index < len(blueprint) else q.course_outcome,
                "bloom_level": blueprint[index].rbt if index < len(blueprint) else q.bloom_level,
                "difficulty": "balanced",
                "module_number": blueprint[index].module if index < len(blueprint) else q.module_number,
                "question_number": blueprint[index].question_number if index < len(blueprint) else (index + 1),
                "subpart": blueprint[index].subpart if index < len(blueprint) else "",
                "section_label": blueprint[index].label if index < len(blueprint) else str(index + 1),
                "confidence": getattr(q, "_confidence", None),
                "source_documents": getattr(q, "_source_documents", []),
                "figure_image_paths": getattr(q, "_figure_image_paths", []),
                "validation_warnings": getattr(q, "_validation_warnings", []),
                "blueprint_slot": blueprint[index] if index < len(blueprint) else None
            }
            for index, q in enumerate(questions)
        ]

        client = OllamaClient()
        if allow_ai_rewrite and await client.is_available():
            rewritten = await client.rephrase_questions(
                questions_data,
                subject.name or "Subject",
                subject.code or "N/A",
                semester,
                exam_type,
                prompt,
            )
            if rewritten:
                questions_data = [
                    {**original, "text": rewritten_item.get("text", original["text"])}
                    for original, rewritten_item in zip(questions_data, rewritten)
                ]

        questions_data = [
            {
                "id": item.get("id"),
                "text": item["text"],
                "marks": item["marks"],
                "course_outcome": item.get("course_outcome", ""),
                "bloom_level": item.get("bloom_level", ""),
                "module_number": item.get("module_number"),
                "difficulty": item.get("difficulty"),
                "question_number": item.get("question_number"),
                "subpart": item.get("subpart"),
                "section_label": item.get("section_label"),
                "confidence": item.get("confidence"),
                "source_documents": item.get("source_documents", []),
                "figure_image_paths": item.get("figure_image_paths", []),
                "validation_warnings": item.get("validation_warnings", []),
                "blueprint_slot": item.get("blueprint_slot"),
            }
            for item in questions_data
        ]

        real_coverage_stats = compute_paper_analytics(questions_data, modules, rbt_dict, co_targets)

        config = PaperConfig(
            department=dept_name,
            subject=subject.name,
            subject_code=subject.code,
            semester=semester,
            max_marks=max_marks,
            duration=f"{duration_minutes} Minutes",
            date=exam_date_parsed.strftime("%d-%m-%Y") if exam_date_parsed else "To be announced",
            batch=batch,
            teaching_department=teaching_department,
            exam_type=exam_type,
            modules=modules,
            rbt_levels=rbt_dist,
            co_targets=list(co_targets.keys()),
            instructions=instructions,
            co_descriptions=co_descriptions,
            co_percentages=real_coverage_stats.get("percentages", {}).get("co", {}),
            module_percentages=real_coverage_stats.get("percentages", {}).get("modules", {}),
            template_note=(
                "Answer any FIVE full questions, choosing at ONE question from each MODULE"
                if max_marks >= 100
                else None
            ),
            template_family="semester-end" if max_marks >= 100 else "internal-assessment",
        )

        output_path = Path(settings.storage_path) / "papers"
        docx_path = generate_question_paper(config, questions_data, output_path)

        paper = QuestionPaper(
            subject_id=subject_id,
            teacher_id=user.id,
            title=title,
            exam_type=exam_type,
            semester=semester,
            batch=batch,
            max_marks=max_marks,
            duration_minutes=duration_minutes,
            exam_date=exam_date_parsed,
            teaching_department=teaching_department,
            prompt_used=prompt,
            generated_summary=(
                f"{'Manually selected' if manual_question_ids else 'AI selected'} "
                f"{len(questions_data)} slot-aligned questions for {subject.code} across "
                f"{len({q.get('module_number') for q in questions_data})} modules."
            ),
            ai_config_json={
                "rbt_levels": rbt_dist,
                "module_numbers": modules,
                "co_targets": co_targets,
                "co_descriptions": co_descriptions,
                "difficulty": {q.get("bloom_level", "L3"): derive_difficulty(q.get("bloom_level", "L3")) for q in questions_data},
                "exam_style": planned_blueprint.pattern,
                "planned_blueprint": {
                    "pattern": planned_blueprint.pattern,
                    "blocks": [
                        {
                            "qno": block.qno,
                            "module": block.module,
                            "type": block.type,
                            "is_or": block.is_or,
                            "labels": [task.label for task in block.subquestions],
                        }
                        for block in planned_blueprint.blocks
                    ],
                },
                "manual_question_ids": manual_question_ids,
                "instructions": instructions,
                "template_note": (
                    "Answer any FIVE full questions, choosing at least ONE question from each MODULE"
                    if max_marks >= 100
                    else None
                ),
                "coverage_stats": real_coverage_stats,
            },
            status=PaperStatus.DRAFT,
            download_path=str(docx_path),
        )
        db.add(paper)
        db.flush()

        from .models import PaperQuestion

        for idx, q_data in enumerate(questions_data, 1):
            slot = blueprint[idx - 1] if idx <= len(blueprint) else None
            db.add(
                PaperQuestion(
                    paper_id=paper.id,
                    question_id=q_data.get("id"),
                    order_index=idx,
                    section_label=str(slot.label) if slot else str(idx),
                    option_group=f"MODULE-{slot.module}-Q{(slot.question_number + 1) // 2}" if slot else f"MODULE-CUSTOM-Q{idx}",
                    custom_marks=slot.marks if slot else q_data.get("marks", 5),
                    question_text_snapshot=q_data.get("text", ""),
                )
            )

        db.commit()

        paper = db.scalar(
            select(QuestionPaper)
            .options(selectinload(QuestionPaper.questions))
            .where(QuestionPaper.id == paper.id)
        )
        
        logger.info("FINAL QUESTIONS:")
        logger.info(len(questions_data))
        logger.info("QUESTION TYPES:")
        logger.info([q.get("question_type", "theory") for q in questions_data])
        
        return serialize_paper(db, paper)
        
    except Exception as e:
        logger.exception("FULL GENERATE PAPER ERROR")
        return JSONResponse(
            status_code=500,
            content={
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
        )

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
