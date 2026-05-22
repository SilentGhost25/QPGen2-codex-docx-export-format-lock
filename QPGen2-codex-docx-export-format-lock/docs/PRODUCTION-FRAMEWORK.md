# QPGen Production Framework
## Enterprise-Grade AI Question Paper Generator for College Networks

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [System Architecture](#system-architecture)
3. [AI Pipeline - Llama 3.2 Vision](#ai-pipeline---llama-32-vision)
4. [Multi-College Architecture](#multi-college-architecture)
5. [Database Schema Enhancement](#database-schema-enhancement)
6. [API Gateway & Services](#api-gateway--services)
7. [Deployment Infrastructure](#deployment-infrastructure)
8. [Security Framework](#security-framework)
9. [Integration Capabilities](#integration-capabilities)
10. [Monitoring & Analytics](#monitoring--analytics)
11. [Implementation Roadmap](#implementation-roadmap)

---

## 1. Executive Summary

### Vision
Transform QPGen from a single-institution prototype into a **multi-tenant, production-grade platform** serving multiple colleges with:
- AI-powered question extraction using Llama 3.2 Vision
- Centralized question bank repository across institutions
- Standardized question paper generation with RBT/CO mapping
- Compliance with NBA/NAAC accreditation requirements
- Enterprise security and 99.9% uptime SLA

### Key Goals
1. **Multi-College Support** - Single deployment serving 50+ colleges
2. **AI Excellence** - 95%+ accuracy in question extraction
3. **Scalability** - Handle 10,000+ concurrent users
4. **Compliance** - NBA CO-PO mapping, NAAC Criteria 2 reporting
5. **Integration** - Connect with existing college ERPs

---

## 2. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │   Web App   │  │  Mobile PWA │  │   Admin     │  │  API        │   │
│  │   (React)   │  │   (React)   │  │   Portal    │  │   Clients   │   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │
└─────────┼────────────────┼────────────────┼────────────────┼───────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       API GATEWAY LAYER                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Kong / Traefik                                │   │
│  │   - Rate Limiting  - Authentication  - Load Balancing          │   │
│  │   - SSL Termination - Request Routing  - Caching                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       SERVICE LAYER                                     │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐│
│  │ Auth Service  │ │ College       │ │ Question      │ │ Paper       ││
│  │ (JWT, SSO)    │ │ Service       │ │ Service       │ │ Service     ││
│  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────┘│
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌─────────────┐│
│  │ AI Processing │ │ Notification  │ │ Analytics     │ │ Export      ││
│  │ Service       │ │ Service       │ │ Service       │ │ Service     ││
│  └───────────────┘ └───────────────┘ └───────────────┘ └─────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │
│  │ PostgreSQL  │  │  Redis      │  │  S3/MinIO   │  │   Elasticsearch│ │
│  │ (Primary DB)│  │ (Cache/Sess)│  │ (Documents) │  │ (Search/Logs)│  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI/ML INFRASTRUCTURE                                │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Ollama Cluster (GPU Nodes)                   │   │
│  │   - Llama 3.2 Vision (Primary)                                 │   │
│  │   - Fallback Models (Llama 3.1, Mistral)                      │   │
│  │   - Auto-scaling based on load                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | React 19 + TypeScript | Web Application |
| **Mobile** | React Native / PWA | Mobile Access |
| **API Gateway** | Kong / Traefik | API Management |
| **Backend** | FastAPI (Python) | REST API Services |
| **Auth Service** | Keycloak / Custom JWT | Authentication/SSO |
| **Database** | PostgreSQL 15 | Primary Data Store |
| **Cache** | Redis 7 | Session/API Cache |
| **Object Storage** | MinIO / S3 | Document Storage |
| **Search** | Elasticsearch | Full-text Search |
| **AI Engine** | Ollama + Llama 3.2 Vision | Question Extraction |
| **Message Queue** | Celery + Redis | Async Processing |
| **Container** | Docker + Kubernetes | Deployment |
| **Monitoring** | Prometheus + Grafana | Observability |

---

## 3. AI Pipeline - Llama 3.2 Vision

### Overview
The AI pipeline is the core differentiator. It handles:
1. **Ingestion** - Read question banks (PDF, DOCX, Images)
2. **Extraction** - Parse questions with Llama 3.2 Vision
3. **Enrichment** - Auto-tag with RBT levels, CO, difficulty
4. **Validation** - Human review loop for accuracy
5. **Generation** - Create balanced question papers

### Llama 3.2 Vision Integration

#### Model Configuration
```python
# backend/app/services.py - Enhanced OllamaService

OLLAMA_CONFIG = {
    "model": "llama3.2-vision",
    "base_url": "http://ollama-cluster:11434",
    "timeout": 120,
    "max_retries": 3,
    "fallback_models": ["llama3.1:70b", "mistral-large"],
    "gpu_memory_threshold": 0.8,  # 80% GPU memory usage
}
```

#### Question Extraction Prompt Engineering

```python
EXTRACTION_PROMPT = """
You are an expert academic parser for engineering question banks.

## TASK
Extract ALL questions from the input document and return JSON.

## INPUT TYPES SUPPORTED
- PDF text from question banks
- Scanned images of question papers
- DOCX files with questions
- Handwritten question images

## OUTPUT SCHEMA
{
  "questions": [
    {
      "text": "Complete question text exactly as in source",
      "marks": number (1-30),
      "bloom_level": "L1-L6",
      "difficulty": "easy|medium|hard",
      "module_number": 1-10,
      "course_outcome": "CO1-CO6",
      "question_type": "theory|problem|objective|case_study",
      "tags": ["additional", "tags"],
      "confidence": 0.0-1.0,
      "source_location": "page_number or section"
    }
  ],
  "metadata": {
    "total_pages": number,
    "subject": "detected or inferred subject",
    "difficulty_distribution": {"easy": %, "medium": %, "hard": %},
    "bloom_distribution": {"L1": count, "L2": count, ...}
  }
}

## BLOOM'S TAXONOMY MAPPING
- L1 (Remember): Define, List, State, Name, Recall, Identify
- L2 (Understand): Explain, Describe, Discuss, Summarize, Interpret
- L3 (Apply): Solve, Calculate, Demonstrate, Execute, Implement
- L4 (Analyze): Compare, Distinguish, Examine, Test, Analyze
- L5 (Evaluate): Evaluate, Judge, Assess, Critique, Justify
- L6 (Create): Design, Construct, Develop, Formulate, Compose

## COURSE OUTCOMES (Standard Engineering)
CO1: Remember and understand fundamental concepts
CO2: Apply knowledge to solve problems
CO3: Analyze and interpret data
CO4: Design solutions for engineering problems
CO5: Evaluate and justify approaches
CO6: Create innovative solutions

## RULES
1. Extract EVERY question, no matter how small
2. Preserve original wording exactly
3. Estimate marks if not explicitly stated (use question length as guide)
4. Assign confidence score based on clarity (1.0 = very clear, 0.5 = ambiguous)
5. If image is unreadable, mark with confidence: 0 and note: "unreadable"

Return ONLY valid JSON. No additional text.
"""

IMAGE_EXTRACTION_PROMPT = """
You are LLaVA 3.2 Vision analyzing an academic question paper image.

## INSTRUCTIONS
1. Carefully read ALL text in the image
2. Identify each numbered question
3. Extract complete question text including any sub-parts (a, b, c...)
4. Note any diagrams, tables, or figures mentioned

## OUTPUT
Return the same JSON schema as the text extraction prompt.

## IF IMAGE IS UNCLEAR
- Still attempt to extract visible content
- Set confidence to 0.3-0.5
- Add note in "tags": ["partial_extraction"]
"""
```

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AI PROCESSING PIPELINE                            │
└─────────────────────────────────────────────────────────────────────────┘

     ┌──────────┐     ┌──────────────┐     ┌──────────────────────┐
     │  Upload  │────▶│   Validate   │────▶│   Format Detection   │
     │ Document │     │   File Type  │     │   (PDF/DOCX/IMG)     │
     └──────────┘     └──────────────┘     └──────────────────────┘
                                                      │
                                                      ▼
                    ┌──────────────────────────────────────────────┐
                    │              CONTENT EXTRACTION               │
                    │  ┌─────────────┐   ┌─────────────────────┐   │
                    │  │   PDF/DOCX  │   │   Images (Vision)   │   │
                    │  │   (PyPDF2)  │   │   (Llama 3.2 Vision)│   │
                    │  └─────────────┘   └─────────────────────┘   │
                    └──────────────────────────────────────────────┘
                                           │
                                           ▼
                    ┌──────────────────────────────────────────────┐
                    │           Llama 3.2 Vision Processing        │
                    │  ┌────────────────────────────────────────┐  │
                    │  │  1. Send image/text to Ollama          │  │
                    │  │  2. Parse JSON response                 │  │
                    │  │  3. Validate schema compliance          │  │
                    │  │  4. Fallback if failed                  │  │
                    │  └────────────────────────────────────────┘  │
                    └──────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴───────────────────────┐
                    │              POST-PROCESSING                   │
                    │  - Normalize bloom levels (L1-L6)            │
                    │  - Validate course outcomes (CO1-CO6)        │
                    │  - Check mark allocation                     │
                    │  - Deduplicate similar questions              │
                    └───────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴───────────────────────┐
                    │              QUALITY ASSURANCE                 │
                    │  ┌──────────────────────────────────────────┐ │
                    │  │  Confidence >= 0.8: Auto-approve          │ │
                    │  │  Confidence 0.5-0.8: Teacher review      │ │
                    │  │  Confidence < 0.5: Manual entry           │ │
                    │  └──────────────────────────────────────────┘ │
                    └───────────────────────────────────────────────┘
                                           │
                    ┌──────────────────────┴───────────────────────┐
                    │              DATABASE STORAGE                  │
                    │  - Insert into questions table                │
                    │  - Link to subject & college                  │
                    │  - Create version history                     │
                    │  - Update search index                        │
                    └───────────────────────────────────────────────┘
```

### Error Handling & Fallback

```python
class QuestionExtractionPipeline:
    def __init__(self):
        self.primary_model = "llama3.2-vision"
        self.fallback_models = ["llama3.1:70b", "mistral-large"]
        
    async def extract(self, file: UploadFile) -> ExtractionResult:
        # Try primary model first
        try:
            result = await self._extract_with_model(
                self.primary_model, 
                file,
                use_vision=file_is_image(file)
            )
            if result.confidence >= 0.8:
                return result
        except ModelUnavailableError:
            pass
        
        # Fallback chain
        for model in self.fallback_models:
            try:
                return await self._extract_with_model(model, file, use_vision=False)
            except:
                continue
        
        # Final fallback: heuristic parsing
        return self._heuristic_fallback(file)
    
    async def _extract_with_model(self, model: str, file: UploadFile, use_vision: bool):
        # Implementation with timeout and retries
        pass
```

### Batch Processing

```python
# Handle bulk uploads from multiple teachers
class BatchExtractionService:
    async def process_question_bank(self, files: list[UploadFile], subject_id: int):
        tasks = []
        for file in files:
            task = asyncio.create_task(
                self.extraction_pipeline.extract(file)
            )
            tasks.append((file.filename, task))
        
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
        
        # Aggregate results
        successful = []
        failed = []
        for (filename, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                failed.append({"filename": filename, "error": str(result)})
            else:
                successful.append(result)
        
        return BatchResult(successful=successful, failed=failed)
```

---

## 4. Multi-College Architecture

### Multi-Tenancy Model

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     MULTI-COLLEGE ARCHITECTURE                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       SUPER ADMIN (Platform)                          │
│  - Manage all colleges                                               │
│  - Platform settings                                                 │
│  - Billing & subscription                                            │
│  - Global analytics                                                  │
└─────────────────────────────────────────────────────────────────────┘
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│   COLLEGE A    │   │   COLLEGE B    │   │   COLLEGE C    │
│   (Tenant 1)   │   │   (Tenant 2)   │   │   (Tenant 3)   │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ • Admin        │   │ • Admin        │   │ • Admin        │
│ • HODs         │   │ • HODs         │   │ • HODs         │
│ • Teachers     │   │ • Teachers     │   │ • Teachers     │
│ • Departments  │   │ • Departments  │   │ • Departments  │
│ • Subjects     │   │ • Subjects     │   │ • Subjects     │
└─────────────────┘   └─────────────────┘   └─────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     SHARED QUESTION BANK                             │
│  - Institution-wide questions                                       │
│  - Cross-department sharing                                         │
│  - Quality-approved questions                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Isolation Strategies

```python
# Option 1: Schema Isolation (PostgreSQL Schema per College)
class CollegeSchemaMiddleware:
    def __call__(self, request, call_next):
        college_id = get_college_from_jwt(request)
        request.state.college_id = college_id
        request.state.db_schema = f"college_{college_id}"
        return await call_next(request)

# Option 2: Row-Level Security (RLS)
# PostgreSQL RLS policy for questions table
CREATE POLICY college_isolation ON questions
USING (college_id = current_setting('app.current_college_id'));

# Option 3: Separate Database (for strict isolation)
# Each college gets own database instance
```

### College Management Service

```python
class CollegeService:
    async def create_college(self, data: CollegeCreate) -> College:
        # Create college tenant
        college = College(
            name=data.name,
            code=data.code,  # Unique identifier (e.g., "DSATM", "RVCE")
            domain=data.domain,  # For SSO
            logo_url=data.logo_url,
            settings=json.dumps(data.settings)
        )
        
        # Initialize schema
        await self._init_college_schema(college)
        
        # Create default admin
        await self._create_college_admin(college, data.admin_email)
        
        return college
    
    async def _init_college_schema(self, college: College):
        # Create PostgreSQL schema for college
        # Seed default data (departments, subjects template)
        pass
    
    def get_college_context(self, college_id: int) -> CollegeContext:
        # Returns college-specific config, theme, settings
        pass
```

---

## 5. Database Schema Enhancement

### Enhanced Entity Relationship

```python
# backend/app/models.py - Enhanced Models

from sqlalchemy import Index, UniqueConstraint
from enum import StrEnum

class InstitutionType(StrEnum):
    ENGINEERING = "engineering"
    MEDICAL = "medical"
    ARTS = "arts"
    SCIENCE = "science"
    POLYTECHNIC = "polytechnic"
    UNIVERSITY = "university"

class College(Base):
    __tablename__ = "colleges"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # DSATM, RVCE
    institution_type: Mapped[InstitutionType] = mapped_column(Enum(InstitutionType))
    domain: Mapped[str] = mapped_column(String(100))  # For SSO
    logo_url: Mapped[str] = mapped_column(String(500))
    address: Mapped[str] = mapped_column(Text)
    contact_email: Mapped[str] = mapped_column(String(200))
    contact_phone: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")
    settings_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    
    departments: Mapped[list["Department"]] = relationship(back_populates="college")
    users: Mapped[list["User"]] = relationship(back_populates="college")
    question_banks: Mapped[list["QuestionBank"]] = relationship(back_populates="college")


class Department(Base):
    __tablename__ = "departments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20))  # AIML, CSE, ECE
    head_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    code_prefix: Mapped[str] = mapped_column(String(10))  # For subject codes (21, 22...)
    
    college: Mapped["College"] = relationship(back_populates="departments")
    subjects: Mapped[list["Subject"]] = relationship(back_populates="department")
    
    __table_args__ = (
        UniqueConstraint("college_id", "code", name="uq_dept_college_code"),
    )


class Subject(Base):
    __tablename__ = "subjects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    dept_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(String(20))  # 21AI51, 21CS52
    semester: Mapped[int] = mapped_column(Integer)
    credits: Mapped[int | None] = mapped_column(Integer)
    max_marks: Mapped[int] = mapped_column(Integer, default=50)
    
    # Curriculum mapping
    course_outcomes: Mapped[list[str]] = mapped_column(JSON, default=list)  # ["CO1", "CO2", ...]
    po_mapping: Mapped[dict] = mapped_column(JSON, default=dict)  # {"CO1": ["PO1", "PO2"]}
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    department: Mapped["Department"] = relationship(back_populates="subjects")
    questions: Mapped[list["Question"]] = relationship(back_populates="subject")
    papers: Mapped[list["QuestionPaper"]] = relationship(back_populates="subject")
    
    __table_args__ = (
        UniqueConstraint("college_id", "code", name="uq_subject_college_code"),
        Index("ix_subject_dept_semester", "dept_id", "semester"),
    )


class QuestionBank(Base):
    __tablename__ = "question_banks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    
    # Document reference
    document_path: Mapped[str] = mapped_column(String(500))
    document_hash: Mapped[str] = mapped_column(String(64))  # For deduplication
    
    # Statistics
    total_questions: Mapped[int] = mapped_column(Integer, default=0)
    verified_questions: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, completed, failed
    processing_error: Mapped[str | None] = mapped_column(Text)
    
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    verified_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    
    college: Mapped["College"] = relationship(back_populates="question_banks")
    subject: Mapped["Subject"] = relationship()
    questions: Mapped[list["Question"]] = relationship(back_populates="source_bank")


class Question(Base):
    __tablename__ = "questions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    source_bank_id: Mapped[int | None] = mapped_column(ForeignKey("question_banks.id"))
    
    text: Mapped[str] = mapped_column(Text)
    marks: Mapped[int] = mapped_column(Integer)
    
    # Academic mapping
    course_outcome: Mapped[str] = mapped_column(String(10))  # CO1-CO6
    bloom_level: Mapped[str] = mapped_column(String(5))  # L1-L6
    difficulty: Mapped[str] = mapped_column(String(20))  # easy, medium, hard
    module_number: Mapped[int] = mapped_column(Integer)
    
    # Quality metrics
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_notes: Mapped[str | None] = mapped_column(Text)
    
    # Content metadata
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    question_type: Mapped[str] = mapped_column(String(30))  # theory, problem, objective
    
    # Source information
    source_text: Mapped[str | None] = mapped_column(Text)  # Original text if modified
    source_page: Mapped[int | None] = mapped_column(Integer)
    
    # Tracking
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    
    subject: Mapped["Subject"] = relationship(back_populates="questions")
    source_bank: Mapped["QuestionBank"] = relationship(back_populates="questions")
    
    __table_args__ = (
        Index("ix_question_subject_bloom", "subject_id", "bloom_level"),
        Index("ix_question_subject_difficulty", "subject_id", "difficulty"),
        Index("ix_question_subject_co", "subject_id", "course_outcome"),
    )


class QuestionPaper(Base):
    __tablename__ = "question_papers"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    
    # Paper metadata
    title: Mapped[str] = mapped_column(String(255))
    exam_type: Mapped[str] = mapped_column(String(50))  # IAT-1, IAT-2, End-Sem
    semester: Mapped[str] = mapped_column(String(20))
    batch: Mapped[str] = mapped_column(String(20))
    max_marks: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer)
    exam_date: Mapped[date | None] = mapped_column(Date)
    teaching_department: Mapped[str] = mapped_column(String(255))
    
    # AI configuration used
    prompt_used: Mapped[str] = mapped_column(Text)
    ai_config_json: Mapped[dict] = mapped_column(JSON)
    generated_summary: Mapped[str] = mapped_column(Text)
    
    # Status workflow
    status: Mapped[PaperStatus] = mapped_column(Enum(PaperStatus), default=PaperStatus.DRAFT)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    review_comments: Mapped[str | None] = mapped_column(Text)
    
    # Export
    download_path: Mapped[str | None] = mapped_column(String(500))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)
    
    subject: Mapped["Subject"] = relationship(back_populates="papers")
    questions: Mapped[list["PaperQuestion"]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[Role] = mapped_column(Enum(Role))
    
    # Extended profile
    employee_id: Mapped[str | None] = mapped_column(String(50))  # College-specific ID
    designation: Mapped[str | None] = mapped_column(String(100))  # Professor, Asst Prof
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    
    college: Mapped["College"] = relationship(back_populates="users")
    department: Mapped[Department | None] = relationship()
```

### Indexing Strategy

```python
# Performance indexes for common queries
Index("ix_questions_college_bloom", "college_id", "bloom_level"),
Index("ix_questions_college_difficulty", "college_id", "difficulty"),
Index("ix_questions_college_co", "college_id", "course_outcome"),
Index("ix_papers_college_status", "college_id", "status"),
Index("ix_papers_college_subject", "college_id", "subject_id"),
Index("ix_users_college_role", "college_id", "role"),
```

---

## 6. API Gateway & Services

### Service Architecture

```python
# backend/app/main.py - Microservices Pattern

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="QPGen Platform", version="2.0.0")

# Service registration
SERVICES = {
    "auth": "http://auth-service:8001",
    "college": "http://college-service:8002",
    "questions": "http://question-service:8003",
    "papers": "http://paper-service:8004",
    "ai": "http://ai-service:8005",
    "analytics": "http://analytics-service:8006",
}

# API Router Structure
API_V1 = APIRouter(prefix="/api/v1")

# Auth routes
API_V1.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# College management routes (Super Admin)
API_V1.include_router(college.router, prefix="/colleges", tags=["Colleges"])

# Institution-specific routes
API_V1.include_router(institution.router, prefix="/institution", tags=["Institution"])

# Questions routes
API_V1.include_router(questions.router, prefix="/questions", tags=["Questions"])

# Papers routes
API_V1.include_router(papers.router, prefix="/papers", tags=["Papers"])

# AI Processing routes
API_V1.include_router(ai.router, prefix="/ai", tags=["AI Processing"])

# Analytics routes
API_V1.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
```

### Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| **Authentication** | | |
| POST | `/api/v1/auth/login` | User login |
| POST | `/api/v1/auth/refresh` | Refresh token |
| POST | `/api/v1/auth/logout` | Invalidate session |
| GET | `/api/v1/auth/sso/{provider}` | SSO login |
| **Colleges (Super Admin)** | | |
| POST | `/api/v1/colleges` | Create college |
| GET | `/api/v1/colleges` | List all colleges |
| GET | `/api/v1/colleges/{id}` | College details |
| PUT | `/api/v1/colleges/{id}` | Update college |
| DELETE | `/api/v1/colleges/{id}` | Deactivate college |
| **Institution** | | |
| GET | `/api/v1/institution/departments` | List departments |
| GET | `/api/v1/institution/subjects` | List subjects |
| GET | `/api/v1/institution/stats` | Institution dashboard |
| **Questions** | | |
| POST | `/api/v1/questions/upload` | Upload question bank |
| GET | `/api/v1/questions` | List questions |
| GET | `/api/v1/questions/{id}` | Question details |
| PUT | `/api/v1/questions/{id}` | Update question |
| DELETE | `/api/v1/questions/{id}` | Delete question |
| POST | `/api/v1/questions/bulk` | Bulk import |
| **Papers** | | |
| POST | `/api/v1/papers/generate` | Generate paper |
| GET | `/api/v1/papers` | List papers |
| GET | `/api/v1/papers/{id}` | Paper details |
| PUT | `/api/v1/papers/{id}` | Update paper |
| POST | `/api/v1/papers/{id}/submit` | Submit for review |
| POST | `/api/v1/papers/{id}/review` | Review paper (HOD) |
| GET | `/api/v1/papers/{id}/download` | Download DOCX/PDF |
| **AI Processing** | | |
| POST | `/api/v1/ai/extract` | Extract questions (async) |
| GET | `/api/v1/ai/jobs/{id}` | Check job status |
| POST | `/api/v1/ai/generate` | Generate with AI |
| **Analytics** | | |
| GET | `/api/v1/analytics/usage` | Usage statistics |
| GET | `/api/v1/analytics/quality` | Question quality metrics |
| GET | `/api/v1/analytics/compliance` | NBA/NAAC reports |

---

## 7. Deployment Infrastructure

### Kubernetes Architecture

```yaml
# k8s/manifests/qpgen-platform.yaml

apiVersion: v1
kind: Namespace
metadata:
  name: qpgen-platform
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: qpgen-config
  namespace: qpgen-platform
data:
  DATABASE_URL: "postgresql://postgres:password@postgres-primary:5432/qpgen"
  REDIS_URL: "redis://redis-cluster:6379"
  OLLAMA_BASE_URL: "http://ollama-cluster:11434"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
  namespace: qpgen-platform
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
      - name: api
        image: qpgen/api-server:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: qpgen-config
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: qpgen-platform
spec:
  replicas: 2
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
      - name: frontend
        image: qpgen/frontend:latest
        ports:
        - containerPort: 3000
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
---
# Ollama GPU Deployment
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ollama-cluster
  namespace: qpgen-ai
spec:
  serviceName: ollama-cluster
  replicas: 2
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      nodeSelector:
        gpu: "true"
      tolerations:
      - key: "nvidia.com/gpu"
        operator: "Exists"
        effect: "NoSchedule"
      containers:
      - name: ollama
        image: ollama/llama3.2-vision:latest
        env:
        - name: OLLAMA_HOST
          value: "0.0.0.0:11434"
        - name: OLLAMA_NUM_PARALLEL"
          value: "4"
        - name: OLLAMA_MAX_LOADED_MODELS"
          value: "2"
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "16Gi"
          requests:
            memory: "8Gi"
        ports:
        - containerPort: 11434
```

### Auto-Scaling Configuration

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
  namespace: qpgen-platform
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
```

### Environment Configuration

```bash
# .env.production

# Application
APP_ENV=production
APP_NAME="QPGen Platform"
APP_URL=https://qpgen.academiccloud.io

# Database
DATABASE_URL=postgresql://user:pass@postgres-primary:5432/qpgen
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10
DATABASE_SSL_MODE=require

# Redis
REDIS_URL=redis://redis-cluster:6379
REDIS_PASSWORD=secret

# Ollama
OLLAMA_BASE_URL=http://ollama-cluster:11434
OLLAMA_MODEL=llama3.2-vision
OLLAMA_TIMEOUT=120

# JWT
JWT_SECRET_KEY=super-secure-secret-key-min-32-chars
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# SSO (Keycloak)
KEYCLOAK_URL=https://keycloak.academiccloud.io
KEYCLOAK_REALM=qpgen

# S3/MinIO
S3_ENDPOINT=https://storage.academiccloud.io
S3_BUCKET=qpgen-documents
S3_ACCESS_KEY=xxx
S3_SECRET_KEY=xxx
S3_REGION=us-east-1

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_PER_HOUR=1000
```

---

## 8. Security Framework

### Authentication Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AUTHENTICATION FLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

  1. Login Options
  ┌─────────────────────────────────────────────────────────────────────┐
  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
  │  │  Email   │  │  SSO     │  │   LDAP   │  │  OAuth   │            │
  │  │  Password│  │(SAML/OIDC)│  │(Corporate)│  │ (Google) │            │
  │  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘            │
  └───────┼─────────────┼─────────────┼─────────────┼───────────────────┘
          │             │             │             │
          ▼             ▼             ▼             ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    Authentication Service                           │
  │  ┌─────────────────────────────────────────────────────────────┐   │
  │  │  1. Validate credentials                                    │   │
  │  │  2. Check college subscription status                       │   │
  │  │  3. Verify user is active                                   │   │
  │  │  4. Generate JWT tokens (access + refresh)                  │   │
  │  │  5. Log audit trail                                         │   │
  │  └─────────────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────────────┘
          │
          ▼
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    Token Response                                    │
  │  {                                                                 │
  │    "access_token": "eyJhbGciOiJIUzI1NiIs...",                       │
  │    "refresh_token": "eyJhbGciOiJIUzI1NiIs...",                      │
  │    "expires_in": 3600,                                             │
  │    "token_type": "bearer"                                           │
  │  }                                                                 │
  └─────────────────────────────────────────────────────────────────────┘
```

### Role-Based Access Control (RBAC)

```python
# backend/app/auth.py - Enhanced RBAC

class Role(StrEnum):
    # Platform roles
    SUPER_ADMIN = "super_admin"  # Platform owner
    
    # College roles
    COLLEGE_ADMIN = "college_admin"  # College IT Admin
    HOD = "hod"  # Head of Department
    TEACHER = "teacher"  # Faculty
    EXAMINER = "examiner"  # External examiner
    
    # Restricted roles
    READONLY = "readonly"  # Audit viewers

# Permission matrix
PERMISSIONS = {
    # Super Admin (Platform)
    Role.SUPER_ADMIN: [
        "college:create", "college:read", "college:update", "college:delete",
        "user:create", "user:read", "user:update", "user:delete",
        "analytics:platform", "settings:platform"
    ],
    
    # College Admin
    Role.COLLEGE_ADMIN: [
        "department:create", "department:read", "department:update",
        "user:create", "user:read", "user:update",
        "questions:read", "questions:bulk_import",
        "papers:read", "papers:export", "papers:approve",
        "analytics:college", "settings:college"
    ],
    
    # HOD
    Role.HOD: [
        "department:read",
        "questions:read", "questions:verify",
        "papers:read", "papers:review", "papers:approve",
        "analytics:department"
    ],
    
    # Teacher
    Role.TEACHER: [
        "questions:create", "questions:read", "questions:update:own",
        "papers:create", "papers:read:own", "papers:update:own",
        "papers:submit"
    ],
}

def require_permission(permission: str):
    def dependency(user: User = Depends(get_current_user)):
        # Check if user role has the permission
        role_perms = PERMISSIONS.get(user.role, [])
        if permission not in role_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission}"
            )
        return user
    return dependency
```

### Security Headers & CORS

```python
# backend/app/main.py

from fastapi.middleware.security import SecurityHeadersMiddleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://*.academiccloud.io", "https://*.college.edu"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    max_age=3600,
)

# Security headers
app.add_middleware(
    SecurityHeadersMiddleware,
    strict_transport_security="max-age=31536000; includeSubDomains",
    content_type_options="nosniff",
    x_frame_options="DENY",
    x_content_type_options="nosniff",
    referrer_policy="strict-origin-when-cross-origin",
)
```

### Data Encryption

```python
# Encryption for sensitive data at rest
from cryptography.fernet import Fernet
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import BYTEA

class EncryptedString(TypeDecorator):
    impl = BYTEA
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(BYTEA(256))
    
    def process_bind_param(self, value, dialect):
        if value:
            return fernet.encrypt(value.encode()).decode()
        return None
    
    def process_result_value(self, value, dialect):
        if value:
            return fernet.decrypt(value.encode()).decode()
        return None

# Usage in model
class User(Base):
    # ... other fields
    aadhaar_encrypted: EncryptedString = mapped_column(EncryptedString, nullable=True)
```

---

## 9. Integration Capabilities

### ERP Integration

```python
# Integration adapters for college ERPs

class ERPAdapter(ABC):
    @abstractmethod
    def sync_users(self) -> list[UserData]:
        pass
    
    @abstractmethod
    def sync_subjects(self) -> list[SubjectData]:
        pass
    
    @abstractmethod
    def push_exam_results(self, results: ExamResultData):
        pass

class SAPB1Adapter(ERPAdapter):
    """Adapter for SAP Business One"""
    
    def sync_users(self) -> list[UserData]:
        # Call SAP B1 API
        pass

class OracleAdapter(ERPAdapter):
    """Adapter for Oracle ERP"""
    
    def sync_users(self) -> list[UserData]:
        # Call Oracle API
        pass

class CustomAdapter(ERPAdapter):
    """Adapter for custom/colleges ERP"""
    
    def sync_users(self) -> list[UserData]:
        # Call REST API
        pass
```

### Notification System

```python
# Async notifications via message queue
class NotificationService:
    def __init__(self):
        self.queue = RedisQueue("notifications")
    
    async def send(self, event: NotificationEvent):
        await self.queue.put(event.dict())
    
    async def process(self):
        while True:
            event = await self.queue.get()
            await self._deliver(event)

class NotificationEvent(BaseModel):
    event_type: str  # paper_submitted, paper_approved, question_verified
    user_id: int
    college_id: int
    data: dict
    channels: list[str] = ["email", "sms", "push"]  # email, sms, push, whatsapp

# Event handlers
async def on_paper_submitted(event: NotificationEvent):
    await notification_service.send(NotificationEvent(
        event_type="paper_submitted",
        user_id=event.data["hod_id"],
        college_id=event.college_id,
        data={"paper_title": event.data["title"], "teacher": event.data["teacher"]},
        channels=["email"]
    ))
```

### Export Formats

```python
# Multiple export options
class ExportService:
    async def export_paper(
        paper_id: int, 
        format: str,  # docx, pdf, html, latex
        template: str = "standard"  # standard, vtu, anna_university, custom
    ) -> bytes:
        
        paper = await self.get_paper(paper_id)
        
        if format == "docx":
            return await self._export_docx(paper, template)
        elif format == "pdf":
            return await self._export_pdf(paper, template)
        elif format == "latex":
            return await self._export_latex(paper, template)
    
    async def _export_docx(self, paper, template):
        doc = DocxTemplate(template)
        return doc.render(paper=paper)
```

---

## 10. Monitoring & Analytics

### Logging Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       LOGGING ARCHITECTURE                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────────┐
│   App Logs  │    │ Access Logs │    │ Audit Logs  │    │ AI Logs    │
│  (Python)   │    │   (Nginx)   │    │  (Custom)   │    │ (Ollama)   │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬───────┘
       │                  │                  │                  │
       └──────────────────┼──────────────────┼──────────────────┘
                          ▼
               ┌─────────────────────────┐
               │     Fluent Bit          │
               │   (Log Collector)       │
               └───────────┬─────────────┘
                           │
               ┌───────────┴────────────┐
               ▼                        ▼
        ┌─────────────┐          ┌─────────────┐
        │ Elasticsearch│          │  S3/Object  │
        │  (Search)   │          │   Storage   │
        └─────────────┘          └─────────────┘
               │                        │
               └───────────┬────────────┘
                           ▼
               ┌─────────────────────────┐
               │      Grafana Dashboards │
               └─────────────────────────┘
```

### Metrics Collection

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status', 'college']
)

http_request_duration = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

# AI metrics
ai_extraction_duration = Histogram(
    'ai_extraction_duration_seconds',
    'Question extraction time',
    ['model', 'file_type']
)

ai_extraction_errors = Counter(
    'ai_extraction_errors_total',
    'AI extraction failures',
    ['model', 'error_type']
)

# Queue metrics
queue_size = Gauge(
    'task_queue_size',
    'Pending tasks in queue',
    ['task_type']
)

# Database metrics
db_connection_pool = Gauge(
    'db_connection_pool_used',
    'Database connections in use'
)
```

### Dashboard Panels

```python
# Grafana dashboard JSON
DASHBOARD_PANELS = [
    # Platform Overview
    "Total Colleges", "Active Users", "Papers Generated Today", "Questions Extracted",
    
    # Performance
    "API Response Time (p95)", "AI Extraction Time", "Database Query Time",
    
    # Usage
    "Requests by College", "Papers by Department", "Question Bank Uploads",
    
    # AI Quality
    "Extraction Success Rate", "Auto-approval Rate", "Fallback Usage",
    
    # Errors
    "Error Rate by Type", "Failed AI Jobs", "Failed Paper Generations"
]
```

---

## 11. Implementation Roadmap

### Phase 1: Foundation (Months 1-3)
- [ ] Set up Kubernetes cluster
- [ ] Implement multi-tenant database schema
- [ ] Build core API services
- [ ] Integrate Llama 3.2 Vision for extraction
- [ ] Basic authentication with JWT
- [ ] Frontend core pages

### Phase 2: AI Pipeline (Months 4-5)
- [ ] Enhance Ollama service with better prompts
- [ ] Implement fallback model handling
- [ ] Batch processing for bulk uploads
- [ ] Quality assurance workflow
- [ ] Question bank management

### Phase 3: Multi-College (Months 6-7)
- [ ] College onboarding flow
- [ ] SSO integration (SAML/OIDC)
- [ ] Role-based access control
- [ ] Inter-college question sharing
- [ ] Subscription management

### Phase 4: Enterprise Features (Months 8-9)
- [ ] ERP adapters (SAP, Oracle, etc.)
- [ ] Notification system (email, SMS, push)
- [ ] Advanced analytics
- [ ] Compliance reporting (NBA, NAAC)
- [ ] Multiple export formats

### Phase 5: Production Hardening (Months 10-12)
- [ ] Load testing & optimization
- [ ] Disaster recovery setup
- [ ] Security audit & penetration testing
- [ ] SLA monitoring
- [ ] Documentation & training

---

## Appendix A: Environment Variables

```bash
# Required environment variables for deployment

# Core
NODE_ENV=production
APP_ENV=production

# Database
DATABASE_HOST=postgres-primary
DATABASE_PORT=5432
DATABASE_NAME=qpgen
DATABASE_USER=qpgen_user
DATABASE_PASSWORD=secure_password

# Redis
REDIS_HOST=redis-cluster
REDIS_PORT=6379

# Ollama
OLLAMA_HOST=ollama-cluster
OLLAMA_PORT=11434
OLLAMA_MODEL=llama3.2-vision

# JWT
JWT_SECRET_KEY=your-32-character-secret-key
JWT_ALGORITHM=HS256

# Storage
S3_ENDPOINT=https://storage.example.com
S3_BUCKET=qpgen
S3_ACCESS_KEY=xxx
S3_SECRET_KEY=xxx

# Monitoring
SENTRY_DSN=https://xxx@sentry.io/xxx
PROMETHEUS_ENDPOINT=http://prometheus:9090
```

---

## Appendix B: API Response Standards

```python
# Standard API response format
class APIResponse(BaseModel):
    success: bool
    data: Any | None = None
    message: str | None = None
    errors: list[ErrorDetail] | None = None
    meta: dict | None = None  # pagination, timing

class ErrorDetail(BaseModel):
    field: str
    message: str
    code: str

# Example responses
{
  "success": true,
  "data": {
    "id": 1,
    "name": "Machine Learning",
    "code": "21AI51"
  },
  "message": "Subject retrieved successfully"
}

{
  "success": false,
  "errors": [
    {"field": "email", "message": "Invalid email format", "code": "INVALID_EMAIL"}
  ]
}
```

---

## Appendix C: Question Paper Templates

```python
# Template system for different university formats

TEMPLATES = {
    "standard": {
        "header": "{college_name}\n{department}\n{subject_code} - {subject_name}",
        "title": "{exam_type} Examination",
        "metadata": "Semester: {semester} | Batch: {batch} | Time: {duration} | Max Marks: {max_marks}",
        "question_format": "{number}. {text} ({marks} marks)"
    },
    "vtu": {
        "header": "VISVESVARAYA TECHNOLOGICAL UNIVERSITY\n{college_name}",
        "title": "{subject_code} - {subject_name}\n{exam_type}",
        "instructions": "Answer any {answered_questions} questions out of {total_questions}",
        "question_format": "{number}. {text} [Marks: {marks}]"
    },
    "anna_university": {
        "header": "ANNA UNIVERSITY, CHENNAI - 600 025",
        "title": "TIME: {duration} | MAX MARKS: {max_marks}",
        "sections": ["PART-A", "PART-B", "PART-C"],
        "question_format": "{section}{number}. {text} ({marks})"
    }
}
```

---

*Document Version: 1.0*
*Last Updated: May 2026*
*Authors: QPGen Development Team*