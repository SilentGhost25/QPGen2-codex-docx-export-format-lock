# QPGen: AI-Powered Academic Question Intelligence

A state-of-the-art system designed for higher education institutions to automate the generation, verification, and management of high-quality question papers. QPGen leverages local LLMs (Ollama) to ensure data privacy while providing intelligent RBT mapping and syllabus compliance.

---

## 🏗️ Project Architecture

- **`frontend/qp-maker`**: Premium React 19 + Vite interface with specialized dashboards for Teachers, HODs, and Admins.
- **`backend`**: High-performance FastAPI server with RAG-based question generation and local LLM integration.
- **`docs`**: Institutional templates, RBT guidelines, and technical documentation.
- **`storage`**: Local database and file repository for academic materials.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- **Node.js** (v20+) & **pnpm**
- **Python** (v3.11+)
- **Ollama** (Running locally with `llama3.2:3b`)

### 2. Backend Installation (Windows)
```powershell
# Navigate to backend
cd backend

# Setup Virtual Environment
python -m venv venv
.\venv\Scripts\activate

# Install Dependencies
pip install -r requirements.txt
pip install -e .

# Configure Environment
cp .env.example .env

# Start Server
uvicorn app.main:app --reload
```

### 3. Frontend Installation
```powershell
# Navigate to frontend
cd frontend/qp-maker

# Install and Start
pnpm install
pnpm run dev
```

---

## 💎 Premium Features

- **Zero-Hallucination RAG**: Question generation is strictly constrained by your uploaded syllabus and question banks.
- **Automated Bloom's Mapping**: Intelligent classification of questions into RBT levels (L1-L6).
- **Institutional Workflow**: Seamless approval pipeline from Teacher draft to HOD review and Admin finalization.
- **Live Preview & DOCX Export**: Real-time rendering of question papers with one-click export to high-fidelity Word documents.

---

## 🔐 Demo Credentials
If `ALLOW_DEMO_SEED=true` is set in `.env`:
- **Admin**: `admin@dsatm.edu` / `Admin@123`
- **Teacher**: `teacher@dsatm.edu` / `Teacher@123`
- **HOD**: `hod@dsatm.edu` / `Hod@123`

---

## 📝 License
MIT License - Developed for Advanced Academic Workflows.
