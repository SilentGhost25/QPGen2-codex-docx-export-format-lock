"""
Semantic hierarchical chunking engine for academic documents.

Strategy:
- Heading-aware section parsing to split by logical syllabus modules/topics
- Normalizes and cleans OCR fragments, headers/footers, and symbol leaks
- Inspects and infers microchunk functional types (definition, algorithm, advantages, applications, examples)
- Strictly filters out low-quality and unacademic OCR garbage paragraphs
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .topic_extractor import extract_academic_topic

logger = logging.getLogger("app.academic.chunking")

# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

def count_tokens(text: str) -> int:
    """Approximate token count using whitespace splitting."""
    return len(re.findall(r"\S+", text))


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AcademicChunk:
    """A semantically meaningful chunk of academic text."""
    text: str
    chunk_index: int
    token_count: int
    page_number: int | None = None
    source_section: str | None = None
    # Inferred metadata
    module_number: int | None = None
    topic_name: str | None = None
    bloom_level: str | None = None
    co_mapping: str | None = None
    confidence_score: float = 0.0


# ---------------------------------------------------------------------------
# Heading awareness patterns
# ---------------------------------------------------------------------------

_HEADING_PATTERNS = [
    re.compile(r"^#{1,4}\s+", re.MULTILINE),
    re.compile(r"^(?:Module|MODULE|Unit|UNIT)\s*[-:]?\s*\d+", re.MULTILINE),
    re.compile(r"^(?:Chapter|CHAPTER)\s+\d+", re.MULTILINE),
    re.compile(r"^\d+\.\d+", re.MULTILINE),
    re.compile(r"^[A-Z][A-Z\s]{4,}$", re.MULTILINE),
]

def _is_heading(line: str) -> bool:
    """Check if a line looks like a section heading."""
    stripped = line.strip()
    if not stripped or len(stripped) > 200:
        return False
    return any(pattern.match(stripped) for pattern in _HEADING_PATTERNS)


# ---------------------------------------------------------------------------
# OCR Cleaning and Quality Filters
# ---------------------------------------------------------------------------

BAD_OCR_PATTERNS = [
    re.compile(r"Page \d+", re.IGNORECASE),
    re.compile(r"FIGURE \d+", re.IGNORECASE),
    re.compile(r"\.{3,}"),
]

def clean_ocr(text: str) -> str:
    """Sanitize and clean raw extracted text from OCR fragments and margins."""
    for pattern in BAD_OCR_PATTERNS:
        text = pattern.sub("", text)
    # Deduplicate whitespaces
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_high_quality(text: str) -> bool:
    """Filter out paragraphs dominated by formulas, lists of numbers, or OCR garbage."""
    words = text.split()
    if len(words) < 20:
        return False
    
    # Check alphabetic character density
    alphabetic = sum(1 for c in text if c.isalpha())
    if not text:
        return False
    if alphabetic / len(text) < 0.35:
        return False
        
    return True

def infer_microchunk_type(text: str) -> str:
    """Infers microchunk subtype classification to populate chunk_summary."""
    lower = text.lower()
    if any(kw in lower for kw in ["define", "what is", "definition", "recall", "state the"]):
        return "definition"
    if any(kw in lower for kw in ["algorithm", "step", "procedure", "flowchart", "pseudocode", "mechanism"]):
        return "algorithm"
    if any(kw in lower for kw in ["advantage", "disadvantage", "limitation", "pros", "cons", "trade-off", "benefit"]):
        return "advantages"
    if any(kw in lower for kw in ["application", "use", "applied in", "scenario", "use-case"]):
        return "applications"
    if any(kw in lower for kw in ["example", "solve", "illustration", "numerical", "worked"]):
        return "examples"
    return "concept"


# ---------------------------------------------------------------------------
# Hierarchical Splitters
# ---------------------------------------------------------------------------

def split_by_headings(text: str) -> list[tuple[str, str]]:
    """Split full document text by heading hierarchy."""
    lines = text.split("\n")
    sections: list[tuple[str, list[str]]] = []
    current_heading = "General Introduction"
    current_lines: list[str] = []

    for line in lines:
        if _is_heading(line):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines or current_heading != "General Introduction":
        sections.append((current_heading, current_lines))

    result = []
    for heading, lines_list in sections:
        content = "\n".join(lines_list).strip()
        if content:
            result.append((heading, content))
    return result


# ---------------------------------------------------------------------------
# Core chunking engine
# ---------------------------------------------------------------------------

def semantic_chunk(
    text: str,
    min_tokens: int = 400,
    max_tokens: int = 800,
    overlap_ratio: float = 0.12,
    page_numbers: dict[int, int] | None = None,
) -> list[AcademicChunk]:
    """
    Split academic text into hierarchical, topic-centered semantic chunks.
    """
    if not text or not text.strip():
        return []

    sections = split_by_headings(text)
    if not sections:
        return []

    overlap_tokens = int(max_tokens * overlap_ratio)
    chunks: list[AcademicChunk] = []
    chunk_index = 0

    def _get_overlap_text(words_list: list[str], overlap_size: int) -> str:
        if len(words_list) <= overlap_size:
            return " ".join(words_list)
        return " ".join(words_list[-overlap_size:])

    for heading, content in sections:
        cleaned_content = clean_ocr(content)
        if not is_high_quality(cleaned_content):
            continue

        words = cleaned_content.split()
        total_word_count = len(words)
        
        # If section is small/standard, keep it as a single chunk!
        if total_word_count <= max_tokens:
            chunk_text = " ".join(words)
            page_num = None
            if page_numbers:
                char_offset = text.find(words[0][:20])
                if char_offset >= 0:
                    for offset, page in sorted(page_numbers.items()):
                        if offset <= char_offset:
                            page_num = page
                        else:
                            break

            chunks.append(AcademicChunk(
                text=chunk_text,
                chunk_index=chunk_index,
                token_count=count_tokens(chunk_text),
                page_number=page_num,
                source_section=heading,
                topic_name=extract_academic_topic(heading + " " + chunk_text),
            ))
            chunk_index += 1
        else:
            # Split section semantically using sliding token windows
            pointer = 0
            while pointer < total_word_count:
                window = words[pointer : pointer + max_tokens]
                if len(window) < min_tokens and chunks:
                    # Merge remainder with last chunk if too small
                    last = chunks[-1]
                    last.text += " " + " ".join(window)
                    last.token_count = count_tokens(last.text)
                    break

                chunk_text = " ".join(window)
                page_num = None
                if page_numbers:
                    char_offset = text.find(window[0][:20])
                    if char_offset >= 0:
                        for offset, page in sorted(page_numbers.items()):
                            if offset <= char_offset:
                                page_num = page
                            else:
                                break

                chunks.append(AcademicChunk(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    token_count=count_tokens(chunk_text),
                    page_number=page_num,
                    source_section=heading,
                    topic_name=extract_academic_topic(heading + " " + chunk_text),
                ))
                chunk_index += 1
                pointer += max_tokens - overlap_tokens

    logger.info(
        "Hierarchical chunker created %d topic-centered chunks from %d heading sections.",
        len(chunks), len(sections)
    )
    return chunks
