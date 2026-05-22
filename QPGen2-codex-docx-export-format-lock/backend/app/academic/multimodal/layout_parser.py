"""
Document Layout Parser.

Detects structural block types within a document page:
  heading | paragraph | equation | table | figure | code | list | caption

Strategy (in order of availability):
  1. PaddleOCR PP-StructureV3  — if paddleocr is installed
  2. Heuristic text classifier  — always available, works on extracted text

The heuristic parser is the guaranteed baseline; PaddleOCR is the upgrade
that handles image-based inputs (scanned pages, photos of notes).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("app.academic.multimodal.layout_parser")

# ---------------------------------------------------------------------------
# Block type constants
# ---------------------------------------------------------------------------

BLOCK_TYPE_HEADING   = "heading"
BLOCK_TYPE_PARAGRAPH = "paragraph"
BLOCK_TYPE_EQUATION  = "equation"
BLOCK_TYPE_TABLE     = "table"
BLOCK_TYPE_FIGURE    = "figure"
BLOCK_TYPE_CODE      = "code"
BLOCK_TYPE_LIST      = "list"
BLOCK_TYPE_CAPTION   = "caption"
BLOCK_TYPE_UNKNOWN   = "unknown"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class LayoutBlock:
    """A detected content block on a page."""
    block_type: str                        # one of BLOCK_TYPE_* constants
    text: str = ""                         # raw OCR / extracted text
    bbox: list[float] = field(default_factory=list)  # [x0, y0, x1, y1] in pts
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Heuristic layout parser (always available)
# ---------------------------------------------------------------------------

# Patterns that strongly suggest an equation/formula line
_EQUATION_PATTERNS = [
    re.compile(r"[=+\-*/\\]{1,}.*[a-zA-Z]"),   # algebraic expressions
    re.compile(r"\\[a-zA-Z]+\{"),               # LaTeX commands like \frac{
    re.compile(r"\$.*\$"),                       # inline math
    re.compile(r"∑|∫|∂|∇|α|β|γ|δ|ε|θ|λ|μ|σ|φ|ω|Ω|≈|≤|≥|≠"),  # math symbols
    re.compile(r"\b[A-Z]\s*=\s*[A-Z\d]"),       # X = Y style assignments
    re.compile(r"\d+\s*/\s*\d+"),               # fractions
]

# Patterns for table rows
_TABLE_PATTERN = re.compile(r"\|.*\||\t.*\t")

# Patterns for headings
_HEADING_PATTERN = re.compile(
    r"^(?:(?:module|unit|chapter|section|part)\s+\d+[\.\s]|"
    r"\d+[\.\d]*\s+[A-Z]|"                        # "1.2 Introduction"
    r"[A-Z][A-Z\s]{4,}$)"                          # ALL CAPS heading
)

# Code fence / monospace indicators
_CODE_PATTERN = re.compile(r"```|^\s{4,}[a-z_]+\(|def |class |#include|import |#define")


def _classify_line(line: str) -> str:
    """Classify a single text line into a block type."""
    stripped = line.strip()
    if not stripped:
        return BLOCK_TYPE_UNKNOWN

    # Code
    if _CODE_PATTERN.search(stripped):
        return BLOCK_TYPE_CODE

    # Table row
    if _TABLE_PATTERN.search(stripped):
        return BLOCK_TYPE_TABLE

    # Equation / formula
    for pat in _EQUATION_PATTERNS:
        if pat.search(stripped):
            return BLOCK_TYPE_EQUATION

    # Heading
    if _HEADING_PATTERN.match(stripped) or (
        len(stripped) < 80 and stripped.endswith(":") and stripped[0].isupper()
    ):
        return BLOCK_TYPE_HEADING

    # Caption (short text after Figure / Table label)
    if re.match(r"^(fig(?:ure)?|table|diagram|chart|graph)[\s\.\d]", stripped, re.IGNORECASE):
        return BLOCK_TYPE_CAPTION

    # List item
    if re.match(r"^[\-•*◦▪▸]\s+|^\d+[\.\)]\s+", stripped):
        return BLOCK_TYPE_LIST

    return BLOCK_TYPE_PARAGRAPH


def parse_text_layout(text: str) -> list[LayoutBlock]:
    """
    Parse a flat text string into typed layout blocks using heuristics.

    Groups consecutive lines of the same type into a single block.
    """
    if not text:
        return []

    lines = text.split("\n")
    blocks: list[LayoutBlock] = []
    current_type: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if current_lines and current_type:
            merged = " ".join(l.strip() for l in current_lines if l.strip())
            if merged:
                blocks.append(
                    LayoutBlock(
                        block_type=current_type,
                        text=merged,
                        confidence=0.75,  # heuristic confidence
                    )
                )

    for line in lines:
        if not line.strip():
            flush()
            current_type = None
            current_lines = []
            continue

        line_type = _classify_line(line)

        if line_type == current_type:
            current_lines.append(line)
        else:
            flush()
            current_type = line_type
            current_lines = [line]

    flush()
    return blocks


# ---------------------------------------------------------------------------
# PaddleOCR layout parser (optional upgrade)
# ---------------------------------------------------------------------------

def _try_paddle_layout(image_bytes: bytes) -> list[LayoutBlock] | None:
    """
    Use PaddleOCR PP-Structure for layout detection on a rendered page.

    Returns None if PaddleOCR is not installed, so callers can fall back.
    """
    try:
        import numpy as np
        from PIL import Image
        from paddleocr import PPStructure
    except ImportError:
        return None

    # PaddleOCR type mapping → our block types
    _PADDLE_TYPE_MAP = {
        "title":     BLOCK_TYPE_HEADING,
        "text":      BLOCK_TYPE_PARAGRAPH,
        "figure":    BLOCK_TYPE_FIGURE,
        "figure_caption": BLOCK_TYPE_CAPTION,
        "table":     BLOCK_TYPE_TABLE,
        "table_caption": BLOCK_TYPE_CAPTION,
        "reference": BLOCK_TYPE_PARAGRAPH,
        "equation":  BLOCK_TYPE_EQUATION,
        "header":    BLOCK_TYPE_HEADING,
        "footer":    BLOCK_TYPE_UNKNOWN,
    }

    try:
        img = Image.open(__import__("io").BytesIO(image_bytes)).convert("RGB")
        img_array = np.array(img)

        engine = PPStructure(show_log=False, recovery=False)
        result = engine(img_array)

        blocks: list[LayoutBlock] = []
        for region in result:
            region_type = region.get("type", "text").lower()
            block_type = _PADDLE_TYPE_MAP.get(region_type, BLOCK_TYPE_PARAGRAPH)
            bbox = region.get("bbox", [])

            # Extract text from OCR results within this region
            text = ""
            res = region.get("res", [])
            if isinstance(res, list):
                text = " ".join(
                    item.get("text", "") for item in res if isinstance(item, dict)
                )
            elif isinstance(res, dict):
                text = res.get("text", "")

            blocks.append(
                LayoutBlock(
                    block_type=block_type,
                    text=text.strip(),
                    bbox=list(bbox) if isinstance(bbox, (list, tuple)) else [],
                    confidence=0.90,
                    metadata={"paddle_type": region_type},
                )
            )

        logger.info("PaddleOCR detected %d blocks", len(blocks))
        return blocks

    except Exception as exc:
        logger.warning("PaddleOCR layout detection failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def detect_layout(
    *,
    text: str | None = None,
    image_bytes: bytes | None = None,
) -> list[LayoutBlock]:
    """
    Detect layout blocks from either text or a rendered page image.

    Tries PaddleOCR first (if image_bytes provided and PaddleOCR installed),
    then falls back to heuristic text parsing.

    Args:
        text:        Extracted text string (always used as fallback).
        image_bytes: PNG/JPEG bytes of a rendered page (enables PaddleOCR).

    Returns:
        List of LayoutBlock objects in reading order.
    """
    if image_bytes:
        paddle_result = _try_paddle_layout(image_bytes)
        if paddle_result is not None:
            return paddle_result

    if text:
        return parse_text_layout(text)

    return []
