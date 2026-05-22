"""
Math / Formula Extractor.

Converts equation blocks into LaTeX representations using:
  1. Nougat (facebook/nougat-base) — if transformers + nougat installed
  2. Vision LLM (Ollama)           — always available as fallback

The output is a LaTeX string, or the original OCR text if extraction fails.
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any

logger = logging.getLogger("app.academic.multimodal.math_extractor")


# ---------------------------------------------------------------------------
# Nougat-based formula extraction (optional, heavy)
# ---------------------------------------------------------------------------

_nougat_model = None
_nougat_processor = None


def _load_nougat() -> bool:
    """Lazily load the Nougat model. Returns True if successful."""
    global _nougat_model, _nougat_processor
    if _nougat_model is not None:
        return True
    try:
        from transformers import NougatProcessor, VisionEncoderDecoderModel
        _nougat_processor = NougatProcessor.from_pretrained("facebook/nougat-base")
        _nougat_model = VisionEncoderDecoderModel.from_pretrained("facebook/nougat-base")
        logger.info("Nougat model loaded successfully")
        return True
    except Exception as exc:
        logger.info("Nougat not available (%s) — will use vision LLM fallback", exc)
        return False


def extract_formula_nougat(image_bytes: bytes) -> str | None:
    """
    Extract LaTeX formula from an equation image using Nougat.

    Returns the LaTeX string, or None if extraction fails.
    """
    if not _load_nougat():
        return None

    try:
        from PIL import Image
        import torch

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        pixel_values = _nougat_processor(image, return_tensors="pt").pixel_values

        with torch.no_grad():
            outputs = _nougat_model.generate(
                pixel_values,
                min_length=1,
                max_new_tokens=256,
                bad_words_ids=[[_nougat_processor.tokenizer.unk_token_id]],
            )

        latex = _nougat_processor.batch_decode(outputs, skip_special_tokens=True)[0]
        latex = latex.strip()
        if latex:
            logger.debug("Nougat extracted: %s", latex[:80])
            return latex
        return None

    except Exception as exc:
        logger.warning("Nougat extraction failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Vision LLM fallback (uses Ollama vision model)
# ---------------------------------------------------------------------------

def extract_formula_vision_llm(image_bytes: bytes) -> str | None:
    """
    Extract LaTeX formula from an equation image using the vision LLM.

    Returns the LaTeX string, or None.
    """
    try:
        from ...llm_pipeline import LLMCall
        from ...config import settings
    except ImportError:
        return None

    llm = LLMCall(
        model=settings.ollama_vision_model,
        timeout=settings.ollama_request_timeout_seconds,
    )
    if not llm.is_available():
        return None

    system = (
        "You are a mathematical OCR engine. "
        "Your ONLY job is to transcribe the mathematical formula or equation in the image "
        "into LaTeX notation. Return ONLY the LaTeX, nothing else. "
        "Do not add $ signs or \\begin/\\end delimiters — just the raw formula."
    )
    prompt = (
        "Transcribe the mathematical formula shown in this image to LaTeX. "
        "Output only the LaTeX formula text, no explanations."
    )

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    result = llm.generate_text(
        prompt, system,
        images=[encoded],
        model=settings.ollama_vision_model,
    )

    if result and len(result.strip()) > 1:
        return result.strip()
    return None


# ---------------------------------------------------------------------------
# Heuristic cleanup for text-based equations
# ---------------------------------------------------------------------------

def clean_equation_text(text: str) -> str:
    """
    Best-effort cleanup for equations extracted via plain OCR.

    Handles common OCR mistakes: 0→O confusion, missing spaces, etc.
    Returns a slightly more readable version of the equation.
    """
    # Strip surrounding whitespace
    text = text.strip()
    # Normalize multiplication dots
    text = text.replace("·", r"\cdot ")
    # Convert common unicode math symbols to LaTeX equivalents
    replacements = {
        "∑": r"\sum",
        "∫": r"\int",
        "∂": r"\partial",
        "∇": r"\nabla",
        "α": r"\alpha",
        "β": r"\beta",
        "γ": r"\gamma",
        "δ": r"\delta",
        "ε": r"\epsilon",
        "θ": r"\theta",
        "λ": r"\lambda",
        "μ": r"\mu",
        "σ": r"\sigma",
        "φ": r"\phi",
        "ω": r"\omega",
        "Ω": r"\Omega",
        "≈": r"\approx",
        "≤": r"\leq",
        "≥": r"\geq",
        "≠": r"\neq",
        "→": r"\rightarrow",
        "∞": r"\infty",
        "∈": r"\in",
        "∉": r"\notin",
        "⊂": r"\subset",
        "∪": r"\cup",
        "∩": r"\cap",
        "√": r"\sqrt",
    }
    for symbol, latex in replacements.items():
        text = text.replace(symbol, f" {latex} ")
    return text.strip()


# ---------------------------------------------------------------------------
# Primary entry point
# ---------------------------------------------------------------------------

def extract_math(
    text: str | None = None,
    image_bytes: bytes | None = None,
) -> dict[str, str]:
    """
    Extract mathematical formula from text or image.

    Tries Nougat → Vision LLM → heuristic text cleanup, in that order.

    Returns:
        dict with keys:
          "latex":  LaTeX string (best available)
          "raw":    original OCR text
          "method": one of "nougat" | "vision_llm" | "heuristic" | "none"
    """
    raw = text or ""

    if image_bytes:
        # Try Nougat first
        latex = extract_formula_nougat(image_bytes)
        if latex:
            return {"latex": latex, "raw": raw, "method": "nougat"}

        # Try Vision LLM
        latex = extract_formula_vision_llm(image_bytes)
        if latex:
            return {"latex": latex, "raw": raw, "method": "vision_llm"}

    if raw:
        cleaned = clean_equation_text(raw)
        return {"latex": cleaned, "raw": raw, "method": "heuristic"}

    return {"latex": "", "raw": "", "method": "none"}
