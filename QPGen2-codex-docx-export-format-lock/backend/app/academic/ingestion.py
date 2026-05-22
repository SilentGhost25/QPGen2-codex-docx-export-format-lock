"""
Document ingestion pipeline for the Academic Knowledge Intelligence Layer.

Pipeline:
  Upload → Format Detection → Text Extraction → Cleaning →
  Semantic Chunking → Academic Classification → Storage

Supported formats: PDF, DOCX, PPTX, TXT, MD, PNG, JPG, JPEG
"""

from __future__ import annotations

import io
import logging
import re
import time
import base64
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import settings
from .chunking import AcademicChunk, semantic_chunk, count_tokens
from .classifier import classify_chunk
from ..llm_pipeline import LLMCall
from .models import (
    AcademicDocument,
    ChunkApprovalStatus,
    DocumentType,
    KnowledgeChunk,
    ProcessingStatus,
    SubjectSyllabus,
)

logger = logging.getLogger("app.academic.ingestion")


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(content: bytes) -> tuple[str, int, dict[int, int]]:
    """Extract text from PDF with page tracking.
    
    Returns: (full_text, page_count, char_offset_to_page_map)
    """
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    pages_text: list[str] = []
    page_offsets: dict[int, int] = {}
    offset = 0

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        page_offsets[offset] = page_num
        pages_text.append(text)
        offset += len(text) + 1  # +1 for newline
        
        # Optional: Extract images if PyMuPDF is available
        # This writes to image_chunks.json asynchronously or silently handles errors
        try:
            _extract_and_store_images_pymupdf(content, page_num)
        except Exception as e:
            logger.debug(f"Image extraction skipped or failed: {e}")

    full_text = "\n".join(pages_text)
    return full_text, len(reader.pages), page_offsets

def _extract_and_store_images_pymupdf(content: bytes, page_num: int):
    """
    Helper to extract images using PyMuPDF (fitz) and store in image_chunks.json.
    Very lightweight and isolated.
    """
    import fitz # PyMuPDF
    import json
    import os
    
    doc = fitz.open(stream=content, filetype="pdf")
    page = doc.load_page(page_num - 1)
    images = page.get_images(full=True)
    
    if not images:
        return
        
    chunks_path = Path("image_chunks.json")
    chunks = []
    if chunks_path.exists():
        try:
            with open(chunks_path, "r") as f:
                chunks = json.load(f)
        except json.JSONDecodeError:
            chunks = []
            
    images_dir = Path("static/images")
    images_dir.mkdir(parents=True, exist_ok=True)
    
    for img_index, img in enumerate(images):
        xref = img[0]
        base_image = doc.extract_image(xref)
        image_bytes = base_image["image"]
        image_ext = base_image["ext"]
        
        # Avoid tiny icons
        if len(image_bytes) < 10000:
            continue
            
        image_filename = f"img_{uuid4().hex[:8]}.{image_ext}"
        image_path = images_dir / image_filename
        
        with open(image_path, "wb") as f:
            f.write(image_bytes)
            
        # Extract surrounding text as proxy for VLM
        text_blocks = page.get_text("blocks")
        nearby_text = " ".join([b[4] for b in text_blocks[:3]]).strip().replace("\n", " ")
        
        chunks.append({
            "image_path": str(image_path),
            "page_num": page_num,
            "topic": nearby_text[:100] if nearby_text else "Academic Diagram",
            "caption": "Extracted academic diagram",
            "keywords": ["diagram", "academic", "figure"]
        })
        
    with open(chunks_path, "w") as f:
        json.dump(chunks, f, indent=2)


def extract_text_from_docx(content: bytes) -> tuple[str, int]:
    """Extract text from DOCX files including tables.
    
    Returns: (full_text, estimated_page_count)
    """
    from docx import Document as DocxDocument

    doc = DocxDocument(io.BytesIO(content))
    parts: list[str] = []

    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            parts.append(paragraph.text)

    for table in doc.tables:
        for row in table.rows:
            row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if row_texts:
                parts.append(" | ".join(row_texts))

    full_text = "\n".join(parts)
    # Rough page estimate: ~500 words per page
    est_pages = max(1, len(full_text.split()) // 500)
    return full_text, est_pages


def extract_text_from_pptx(content: bytes) -> tuple[str, int]:
    """Extract text from PPTX files.
    
    Returns: (full_text, slide_count)
    """
    try:
        from pptx import Presentation
    except ImportError:
        logger.warning("python-pptx not installed, cannot extract PPTX text")
        return "", 0

    prs = Presentation(io.BytesIO(content))
    parts: list[str] = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_text = f"\n--- Slide {slide_num} ---\n"
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = paragraph.text.strip()
                    if text:
                        slide_text += text + "\n"
            if shape.has_table:
                for row in shape.table.rows:
                    row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                    if row_texts:
                        slide_text += " | ".join(row_texts) + "\n"
        parts.append(slide_text)

    return "\n".join(parts), len(prs.slides)


def extract_text_from_image(content: bytes) -> str:
    """Extract text from images using OCR.
    
    Tries local OCR first, then falls back to the configured vision model.
    """
    try:
        import pytesseract
        from PIL import Image
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image).strip()
        if text:
            return text
    except ImportError:
        logger.info("pytesseract not installed, image OCR unavailable")
    except Exception as e:
        logger.warning("Image OCR failed: %s", e)

    llm = LLMCall(
        model=settings.ollama_vision_model,
        timeout=settings.ollama_request_timeout_seconds,
    )
    if not llm.is_available():
        return ""

    system = (
        "You are performing OCR for academic material ingestion. "
        "Transcribe the visible text faithfully and do not summarize."
    )
    prompt = (
        "Read the academic image and return only the extracted text. "
        "Preserve headings, lists, and technical terms whenever possible."
    )
    encoded = base64.b64encode(content).decode("utf-8")
    extracted = llm.generate_text(prompt, system, images=[encoded], model=settings.ollama_vision_model)
    return extracted.strip() if extracted else ""


def extract_text(file_name: str, content: bytes) -> tuple[str, int, dict[int, int] | None]:
    """
    Detect file format and extract text.
    
    Returns: (text, page_count, page_offset_map_or_None)
    """
    suffix = Path(file_name).suffix.lower()
    
    if suffix == ".pdf":
        text, pages, offsets = extract_text_from_pdf(content)
        return text, pages, offsets
    elif suffix == ".docx":
        text, pages = extract_text_from_docx(content)
        return text, pages, None
    elif suffix == ".pptx":
        text, slides = extract_text_from_pptx(content)
        return text, slides, None
    elif suffix in {".txt", ".md", ".csv"}:
        text = content.decode("utf-8", errors="ignore")
        pages = max(1, len(text.split()) // 500)
        return text, pages, None
    elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}:
        text = extract_text_from_image(content)
        return text, 1, None
    else:
        text = content.decode("utf-8", errors="ignore")
        return text, 1, None


# ---------------------------------------------------------------------------
# Text Cleaning
# ---------------------------------------------------------------------------

def clean_academic_text(text: str) -> str:
    """Clean extracted text while preserving academic structure."""
    if not text:
        return ""

    # Normalize whitespace within lines (but preserve paragraph breaks)
    lines = text.split("\n")
    cleaned_lines: list[str] = []
    
    for line in lines:
        # Collapse multiple spaces
        line = re.sub(r"[ \t]+", " ", line)
        # Remove control characters except newline
        line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", line)
        cleaned_lines.append(line.strip())

    result = "\n".join(cleaned_lines)
    # Collapse more than 3 consecutive newlines
    result = re.sub(r"\n{4,}", "\n\n\n", result)
    return result.strip()


# ---------------------------------------------------------------------------
# Document Type Detection
# ---------------------------------------------------------------------------

def detect_document_type(file_name: str, text: str) -> DocumentType:
    """Heuristically detect the type of academic document."""
    name_lower = file_name.lower()
    text_lower = text[:3000].lower() if text else ""

    if any(kw in name_lower for kw in ("syllabus", "curriculum")):
        return DocumentType.SYLLABUS
    if any(kw in name_lower for kw in ("previous", "model paper", "past paper", "question paper")):
        return DocumentType.PREVIOUS_PAPER
    if any(kw in name_lower for kw in ("question bank", "qbank", "q-bank")):
        return DocumentType.QUESTION_BANK
    if any(kw in name_lower for kw in ("lab", "manual", "experiment")):
        return DocumentType.LAB_MANUAL
    if name_lower.endswith(".pptx") or name_lower.endswith(".ppt"):
        return DocumentType.PPT

    # Content-based detection
    if any(kw in text_lower for kw in ("syllabus", "course objectives", "course outcomes")):
        return DocumentType.SYLLABUS
    if re.search(r"(?:Q\.?\s*\d|question\s+paper|marks?:?\s*\d)", text_lower):
        return DocumentType.QUESTION_BANK

    return DocumentType.NOTES


# ---------------------------------------------------------------------------
# Main Ingestion Pipeline
# ---------------------------------------------------------------------------

def create_document_record(
    db: Session,
    subject_id: int,
    user_id: int,
    file_name: str,
    content: bytes,
    document_type: DocumentType | None = None,
) -> AcademicDocument:
    """Save the file and create the initial database record immediately."""
    suffix = Path(file_name).suffix.lower()

    # --- Save file ---
    upload_dir = settings.storage_path / "academic" / str(subject_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / f"{uuid4().hex}_{file_name}"
    saved_path.write_bytes(content)

    # --- Create document record ---
    doc = AcademicDocument(
        subject_id=subject_id,
        uploaded_by=user_id,
        file_name=file_name,
        file_type=suffix.lstrip("."),
        document_type=document_type or DocumentType.NOTES,
        storage_path=str(saved_path),
        processing_status=ProcessingStatus.EXTRACTING,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


def process_document_background(
    document_id: int,
    auto_approve_threshold: float = 0.6,
) -> None:
    """
    Background worker for extraction, chunking, classification, and embedding.
    Runs completely separate from the request thread.
    """
    from ..database import SessionLocal
    db = SessionLocal()
    
    try:
        doc = db.get(AcademicDocument, document_id)
        if not doc:
            return

        start_time = time.time()
        file_name = doc.file_name

        try:
            content = Path(doc.storage_path).read_bytes()

            # --- Extract text ---
            text, page_count, page_offsets = extract_text(file_name, content)
            doc.page_count = page_count

            if not text or len(text.strip()) < 50:
                doc.processing_status = ProcessingStatus.FAILED
                doc.processing_error = "Insufficient text extracted from document"
                db.commit()
                return

            # --- Clean text ---
            cleaned = clean_academic_text(text)
            doc.extracted_text = cleaned[:100000]  # Store first 100k chars

            # --- Multimodal structured parsing ---
            doc.processing_status = ProcessingStatus.PARSING
            db.commit()

            try:
                from .multimodal import parse_document_structure
                from ..config import settings

                struct_doc = parse_document_structure(
                    file_name=file_name,
                    content=content,
                    storage_dir=settings.storage_path,
                    analyze_figures=True,
                    extract_math=True,
                )

                # Persist structured content
                doc.structured_content = struct_doc.to_dict()
                doc.has_equations = struct_doc.has_equations
                doc.has_figures = struct_doc.has_figures
                doc.has_tables = struct_doc.has_tables
                doc.equation_count = struct_doc.summary.get("equation_count", 0)
                doc.figure_count = struct_doc.summary.get("figure_count", 0)
                doc.table_count = struct_doc.summary.get("table_count", 0)
                db.commit()

                # Replace plain cleaned text with enriched text for chunking
                # The enriched text embeds [EQUATION:...] and [FIGURE:...] markers
                # so the RAG system can reference visual content in question generation
                enriched = struct_doc.to_enriched_text()
                if enriched and len(enriched.strip()) > 50:
                    cleaned = enriched
                    logger.info(
                        "Multimodal parsing enriched text for '%s': "
                        "%d equations, %d figures, %d tables",
                        file_name,
                        doc.equation_count,
                        doc.figure_count,
                        doc.table_count,
                    )
            except Exception as exc:
                logger.warning(
                    "Multimodal structured parsing failed for '%s', using plain text: %s",
                    file_name, exc,
                )
                # Not fatal — continue with plain text

            # --- Detect document type ---
            if doc.document_type == DocumentType.NOTES:
                doc.document_type = detect_document_type(file_name, cleaned)

            # --- Semantic chunking ---
            doc.processing_status = ProcessingStatus.CHUNKING
            db.commit()

            chunks = semantic_chunk(
                cleaned,
                min_tokens=100,
                max_tokens=250,
                overlap_ratio=0.12,
                page_numbers=page_offsets,
            )

            if not chunks:
                logger.warning(
                    "Semantic chunking produced no chunks for '%s'; creating a fallback chunk",
                    file_name,
                )
                fallback_text = cleaned[:4000].strip()
                if not fallback_text:
                    doc.processing_status = ProcessingStatus.FAILED
                    doc.processing_error = "No meaningful chunks could be created"
                    db.commit()
                    return
                chunks = [
                    AcademicChunk(
                        text=fallback_text,
                        chunk_index=0,
                        token_count=count_tokens(fallback_text),
                        page_number=1,
                        source_section=None,
                    )
                ]

            # --- Load syllabus for classification ---
            syllabus = db.query(SubjectSyllabus).filter_by(subject_id=doc.subject_id).first()
            syllabus_modules = syllabus.modules_json if syllabus else None

            # --- Classify and store chunks ---
            doc.processing_status = ProcessingStatus.EMBEDDING
            db.commit()

            db_chunks = []
            last_detected_module = None
            for chunk in chunks:
                classification = classify_chunk(
                    chunk.text,
                    source_section=chunk.source_section,
                    syllabus_modules=syllabus_modules,
                )

                module_number = classification.module_number
                if module_number is not None:
                    last_detected_module = module_number
                else:
                    module_number = last_detected_module

                approval = (
                    ChunkApprovalStatus.AUTO_APPROVED
                    if classification.confidence_score >= auto_approve_threshold
                    else ChunkApprovalStatus.PENDING_REVIEW
                )

                db_chunk = KnowledgeChunk(
                    document_id=doc.id,
                    subject_id=doc.subject_id,
                    chunk_text=chunk.text,
                    chunk_index=chunk.chunk_index,
                    token_count=chunk.token_count,
                    module_number=module_number,
                    syllabus_unit=None,
                    topic_name=classification.topic_name,
                    bloom_level=classification.bloom_level,
                    co_mapping=classification.co_mapping,
                    page_number=chunk.page_number,
                    confidence_score=classification.confidence_score,
                    approval_status=approval,
                )
                db.add(db_chunk)
                db_chunks.append(db_chunk)

            doc.total_chunks = len(chunks)
            db.commit()

            elapsed = time.time() - start_time
            logger.info(
                "Ingested '%s': %d pages, %d chunks in %.2fs",
                file_name, page_count, len(chunks), elapsed,
            )

            # --- Generate Embeddings ---
            from .embeddings import generate_embeddings_batch
            
            texts = [c.chunk_text for c in db_chunks]
            embeddings = generate_embeddings_batch(texts)
            
            for chunk, embedding in zip(db_chunks, embeddings):
                if embedding is not None:
                    chunk.embedding_vector = embedding
                    
            doc.extracted_text = None  # Discard full extracted text as per guidelines
            doc.processing_status = ProcessingStatus.COMPLETED
            db.commit()
            logger.info("Completed embedding generation for doc %d synchronously in background thread", doc.id)

        except Exception as e:
            logger.error("Ingestion failed for '%s': %s", file_name, e)
            doc.processing_status = ProcessingStatus.FAILED
            doc.processing_error = str(e)[:2000]
            db.commit()

    finally:
        db.close()
