"""
PDF Image Extractor — PyMuPDF-based embedded image extraction.

Extracts all raster images embedded inside PDF pages and returns them
as (page_number, image_index, image_bytes, extension) tuples.

Falls back gracefully if PyMuPDF is not installed.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("app.academic.multimodal.pdf_extractor")


@dataclass
class EmbeddedImage:
    """An image extracted from a PDF page."""
    page_number: int       # 1-indexed
    image_index: int       # position within the page
    image_bytes: bytes
    extension: str         # "png", "jpeg", "jpg", etc.
    width: int
    height: int
    xref: int              # internal PDF xref for deduplication


def extract_images_from_pdf(content: bytes) -> list[EmbeddedImage]:
    """
    Extract all embedded images from a PDF.

    Uses PyMuPDF (fitz) for extraction.  Returns an empty list if
    PyMuPDF is not installed or no images are found.

    Args:
        content: Raw PDF bytes.

    Returns:
        List of EmbeddedImage objects, ordered by (page, position).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.info("PyMuPDF (fitz) not installed — PDF image extraction skipped.")
        return []

    images: list[EmbeddedImage] = []
    seen_xrefs: set[int] = set()

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        logger.warning("Could not open PDF for image extraction: %s", exc)
        return []

    for page_index in range(len(doc)):
        page = doc[page_index]
        page_number = page_index + 1

        try:
            image_list = page.get_images(full=True)
        except Exception as exc:
            logger.warning("Page %d image listing failed: %s", page_number, exc)
            continue

        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]

            # Skip duplicate embedded images (same xref across pages)
            if xref in seen_xrefs:
                continue
            seen_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
            except Exception as exc:
                logger.debug("Could not extract xref=%d: %s", xref, exc)
                continue

            image_bytes = base_image.get("image", b"")
            ext = base_image.get("ext", "png")
            width = base_image.get("width", 0)
            height = base_image.get("height", 0)

            # Skip tiny images (likely decorative bullets, logos < 32px)
            if width < 32 or height < 32:
                continue

            if not image_bytes:
                continue

            images.append(
                EmbeddedImage(
                    page_number=page_number,
                    image_index=img_index,
                    image_bytes=image_bytes,
                    extension=ext,
                    width=width,
                    height=height,
                    xref=xref,
                )
            )

    doc.close()
    logger.info(
        "Extracted %d embedded images from %d-page PDF",
        len(images),
        len(doc) if not doc.is_closed else "?",
    )
    return images


def extract_page_renders(
    content: bytes,
    dpi: int = 150,
    max_pages: int = 50,
) -> list[tuple[int, bytes]]:
    """
    Render each PDF page as a PNG image (for layout analysis).

    This is used when the PDF has no embedded images but we still
    want to run layout detection on the rendered page content.

    Args:
        content: Raw PDF bytes.
        dpi: Resolution for rendering (150 dpi is a good balance).
        max_pages: Maximum pages to render (avoids huge PDFs).

    Returns:
        List of (page_number, png_bytes) tuples.
    """
    try:
        import fitz
    except ImportError:
        logger.info("PyMuPDF not installed — page rendering skipped.")
        return []

    renders: list[tuple[int, bytes]] = []

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except Exception as exc:
        logger.warning("Could not open PDF for rendering: %s", exc)
        return []

    total_pages = min(len(doc), max_pages)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)  # 72 dpi is the default

    for page_index in range(total_pages):
        page = doc[page_index]
        try:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            png_bytes = pix.tobytes("png")
            renders.append((page_index + 1, png_bytes))
        except Exception as exc:
            logger.warning("Page %d render failed: %s", page_index + 1, exc)

    doc.close()
    logger.info("Rendered %d/%d pages at %d dpi", len(renders), total_pages, dpi)
    return renders
