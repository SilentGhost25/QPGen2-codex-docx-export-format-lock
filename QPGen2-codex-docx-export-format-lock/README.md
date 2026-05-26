# QPGen: AI-Powered Academic Question Intelligence System

QPGen is a state-of-the-art, enterprise-grade application built for higher education institutions (such as autonomous engineering colleges) to automate, verify, and regulate the lifecycle of exam question papers. It enforces strict compliance with **Revised Bloom's Taxonomy (RBT)**, **Course Outcomes (CO)**, and institutional policies. 

The system leverages **local Large Language Models (LLMs via Ollama)** to guarantee strict institutional data privacy and security, preventing sensitive academic evaluation data from leaking to third-party APIs.

---

## 🏗️ System Architecture

QPGen is organized as a monorepo containing a high-performance backend, a rich visual frontend, and shared libraries.

```
QPGen Workspace Root
├── backend/                       # FastAPI Server Architecture
│   ├── app/
│   │   ├── academic/              # Academic Domain Core
│   │   │   ├── planning/          # Blueprint Engine & Layout Rules
│   │   │   ├── validation/        # RBT/CO Policy Enforcers & Overlap Detectors
│   │   │   ├── sanitization/      # OCR Cleanup & LLM Artifact Scrubbers
│   │   │   ├── ingestion/         # PDF Syllabus & Material Parsers
│   │   │   ├── retrieval.py       # RAG Vector Search & Chunk Retriever
│   │   │   └── routes.py          # Academic Uploads, Syllabus, & Q-Bank Endpoints
│   │   ├── generator/             # High-Fidelity DOCX Exporter
│   │   ├── utils/                 # Difficulty Mappers & Helpers
│   │   ├── main.py                # FastAPI Main Application (Routes & Endpoints)
│   │   ├── services.py            # Paper Assembly & CRUD Services
│   │   ├── models.py              # SQLAlchemy Core Models (Users, Papers, Questions)
│   │   └── ai_service.py          # Vector Ingestion, Embeddings, & Summary Engine
├── frontend/qp-maker/             # React 19 + TypeScript + Vite Client
│   ├── src/
│   │   ├── components/            # UI Components & Paper Live Previews
│   │   ├── pages/                 # Dashboard, Generate, Analytics, Uploads
│   │   └── utils/                 # Frontend DOCX export libraries
└── storage/                       # Local SQLite Databases & Document Store
```

---

## 🛠️ Deep Dive: Domain Pipelines & Core Engines

### 1. Ingestion & Document Processing (`backend/app/academic/ingestion.py` & `chunking.py`)
* **Multi-Format Parsing:** Extracts text and structures academic resources (Syllabus, Textbooks, Lecture Notes, Reference Papers, and Past Exam Papers) using high-speed PDF/OCR extraction engines.
* **Hierarchical Chunking:** Raw documents are segmented into semantic chunks maintaining structural metadata (e.g., Module number, Page number, Chapter titles).
* **Multimodal Extraction:** Auto-detects diagrams, mathematical equations, and figure placeholders to store them as associated graphical assets.
* **Vector Ingestion:** Text chunks are passed through a local embeddings engine (`sentence-transformers/all-MiniLM-L6-v2`) and indexed in a local vector space for lightning-fast cosine similarity retrieval.

### 2. Planning & Blueprint Engine (`backend/app/academic/planning/blueprint_engine.py`)
* **Slot-Based Structuring:** Rather than letting the LLM output random questions, the system generates a strict structural blueprint containing target slots defined by:
  * **Module Numbers:** Module 1 to Module 5.
  * **Custom Marks Allocation:** E.g., 5+5 marks for Internal Assessment Tests (IAT), or 6+6+8/10+10 for End Semester Exams.
  * **Outcome Target Mapping:** Links slots directly to target Course Outcomes (CO1 to CO5).
  * **Cognitive Complexity (RBT):** Map slots directly to cognitive levels (L1: Remember, L2: Understand, L3: Apply, L4: Analyze, L5: Evaluate, L6: Create).
* **OR/Choice Branches:** Dynamically structures mandatory choices (e.g., Module 1: Question 1a/1b OR Question 2a/2b) in compliance with VTU/Autonomous guidelines.

### 3. Retrieval-Augmented Generation (RAG) (`backend/app/academic/generation.py`)
* **Local Inference Pipeline:** Sends structural directives to Ollama (`mistral` or `llama3.2` models) coupled with context chunks retrieved from the syllabus and notes.
* **Zero-Hallucination Guardrails:** Employs system prompts that restrict the LLM from making up facts. The generated question must contain a trace path back to the sourced document IDs.
* **Dynamic Retries:** If the generated question fails schema validation (wrong marks, mismatching Bloom's Taxonomy keyword, or syntax errors), the system automatically self-corrects by requesting regenerations against the failed slots.

### 4. Policy Validation & Audit Control (`backend/app/academic/validation.py`)
* **Semantic Overlap & Redundancy Check:** Calculates cosine similarity scores between all chosen questions (and questions from a database of previous tests) to flag and block duplicate questions (threshold score $> 0.72$).
* **End-Semester Structural Checks:** Enforces that in 100-mark End-Sem exams, no more than one module can contain 3 subparts (e.g., a, b, c) while the rest must conform to 2 subparts (e.g., a, b).
* **RBT Keyword Enforcer:** Assures that L1 questions use keywords like *"Define"*, *"List"*; L3 questions use *"Apply"*, *"Calculate"*; L4 questions use *"Compare"*, *"Analyze"*, etc.

### 5. Sanitization & Scrubbing (`backend/app/academic/sanitization/response_cleaner.py`)
* **LLM Artifact Stripper:** Uses regex filters to scrub conversational boilerplate, reasoning trails, and training leaks like:
  * *"Here is a question based on..."*
  * *"Considering the provided context..."*
  * OCR leaks, `[EQUATION: ...]` tags, subject/module headers, page numbers, and marks placeholders.
* **Typographical Cleaners:** Restructures whitespace, standardizes bullet lists, and formats mathematical notation before saving questions to database storage.

### 6. High-Fidelity DOCX Exporter (`backend/app/generator/`)
* **DSATM Layout Rules:** Produces publication-grade MS Word documents using python-docx, outputting precise:
  * Institutional letterheads with custom logo alignments (DSU seal, IQAC accredited banners).
  * Auto-calculated USN block inputs.
  * Dynamically spanned choice rows (`"OR"` separators) aligned symmetrically.
  * Standardized grid tables mapping Question Numbers, Marks, COs, and RBT Levels for every question.
  * Inline diagram/image rendering scaled dynamically.

---

## 🚀 Step-by-Step Developer Setup

### 1. System Requirements & Prerequisites
* **Operating System:** Windows 10/11, macOS, or Linux (Ubuntu 22.04+).
* **Runtimes:** Node.js (v20 or v22 LTS) and Python (v3.11 or v3.12).
* **Package Manager:** `pnpm` (Install globally with `npm i -g pnpm`).
* **AI Toolchain:** Download and install [Ollama](https://ollama.com).

### 2. Ollama Setup
Run the following commands in your shell to fetch the models required by the generation pipeline:
```bash
# Pull the default generation model
ollama pull mistral

# Start the service (if not already running in the background)
ollama serve
```

### 3. Backend Setup
Navigate to the `backend` folder, set up your virtual environment, and install core packages:
```powershell
# 1. Open Terminal and navigate to the backend directory
cd backend

# 2. Create and activate a Python virtual environment
python -m venv venv
.\venv\Scripts\activate   # On Linux/macOS: source venv/bin/activate

# 3. Upgrade pip and install all required modules
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 4. Copy the environment template and set your configuration variables
copy .env.example .env    # On Linux/macOS: cp .env.example .env
```
Ensure your `.env` contains:
```env
DATABASE_URL=sqlite:///./storage/qpgen.db
OLLAMA_BASE_URL=http://localhost:11434
ALLOW_DEMO_SEED=true
JWT_SECRET=your_jwt_secret_key_here
```

To run the database migrations and start the backend:
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. Frontend Setup
In a new terminal window:
```bash
# 1. Navigate to the frontend workspace
cd frontend/qp-maker

# 2. Install all node packages via pnpm
pnpm install

# 3. Launch the hot-reloading development server
pnpm run dev
```
Open `http://localhost:5173` in your web browser.

---

## 🔐 Institutional Workflow Roles & Credentials

When `ALLOW_DEMO_SEED=true` is set in the backend environment, you can log in immediately using the following institutional accounts:

| Role | Username | Password | Access Privileges |
| :--- | :--- | :--- | :--- |
| **Teacher** | `teacher@dsatm.edu` | `Teacher@123` | Upload syllabus/notes, generate questions, select blueprints, submit question papers for review. |
| **HOD** | `hod@dsatm.edu` | `Hod@123` | Audit submitted papers, inspect quality/co/rbt dashboards, approve/reject papers with comments. |
| **Admin** | `admin@dsatm.edu` | `Admin@123` | Full dashboard view, subject/faculty database management, archive and export finalized papers. |

---

## 💎 Customizing Institutional Guidelines & Blueprint Rules

* **Bloom's Cognitive Level Mappings:** To alter Bloom's Taxonomy verbs or adjust difficulty parameters, modify `backend/app/academic/policies.py`.
* **Question Layout Structures:** To configure target marks (e.g., implementing a new 70-mark End-Sem structure), edit `buildQuestionBlueprint` inside `frontend/qp-maker/src/pages/generate.tsx` and the corresponding parsing inside `backend/app/academic/planning/blueprint_engine.py`.
* **Document Export Formatting:** To change headers, footers, font sizing, or margin dimensions of the exported Word documents, configure the styling parameters inside `backend/app/generator/question_body_builder.py`.
