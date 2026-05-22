# Project Context

## Goal

Institutional AI question paper generation platform for college faculty, HOD review, and exam-cell export workflows.

## Frontend

- React 19 + TypeScript
- Tailwind CSS + shadcn/ui
- Framer Motion
- TanStack Query

## Backend

- FastAPI service in `backend/`
- JWT auth with teacher, HOD, and admin roles
- SQLite by default for local work, PostgreSQL-ready through `DATABASE_URL`
- Ollama integration targeting `llama3.2-vision`

## Current direction

- Replace mock data with live API integration
- Keep the experience focused on DSATM-style paper generation
- Support document upload, AI-assisted extraction, approval workflow, and DOCX export
