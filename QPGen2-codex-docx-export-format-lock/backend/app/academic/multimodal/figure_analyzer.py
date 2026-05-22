"""
Figure / Diagram Analyzer.

Generates a structured description of academic figures (diagrams, charts,
flowcharts, architecture diagrams, etc.) using the vision LLM.

Output is a JSON-compatible dict:
  {
    "figure_type":  "architecture_diagram",
    "description":  "...",
    "components":   ["Encoder", "Decoder", "Attention"],
    "labels":       ["Q", "K", "V"],
    "caption":      "Figure 1: Transformer block"
  }
"""

from __future__ import annotations

import base64
import logging
from typing import Any

logger = logging.getLogger("app.academic.multimodal.figure_analyzer")


FIGURE_SYSTEM_PROMPT = (
    "You are an academic figure analyst. "
    "Your job is to describe academic figures (diagrams, charts, flowcharts, "
    "block diagrams, architecture diagrams) for use in question generation. "
    "Be precise, technical, and focused on educational content. "
    "Return ONLY valid JSON — no markdown, no prose outside JSON."
)

FIGURE_PROMPT = """\
Analyze this academic figure and return a JSON object with these keys:
- "figure_type": one of [architecture_diagram, flowchart, graph, table, equation_diagram, block_diagram, circuit, waveform, other]
- "description": 2-4 sentence technical description of what the figure shows
- "components": list of major labeled components or nodes in the figure
- "labels": list of mathematical labels, variables, or annotations visible
- "relationships": key relationships or flows shown (e.g. "Input feeds Encoder which connects to Decoder")
- "academic_concepts": academic/technical concepts illustrated

Respond with ONLY the JSON object, no other text.
"""


def analyze_figure(
    image_bytes: bytes,
    nearby_text: str = "",
) -> dict[str, Any]:
    """
    Analyze an academic figure image using the vision LLM.

    Args:
        image_bytes: PNG/JPEG bytes of the figure.
        nearby_text: Surrounding text (caption, section text) for context.

    Returns:
        Structured dict with figure description, components, labels.
        Returns a minimal dict if the vision LLM is unavailable.
    """
    fallback = {
        "figure_type": "other",
        "description": nearby_text[:200] if nearby_text else "Figure extracted from document.",
        "components": [],
        "labels": [],
        "relationships": "",
        "academic_concepts": [],
    }
    logger.info("Multimodal vision LLM pipeline disabled. Returning local technical text-fallback.")
    return fallback


def generate_questions_from_figure(
    figure_analysis: dict[str, Any],
    bloom_level: str = "L3",
) -> list[str]:
    """
    Generate question prompts about a figure (used during generation enrichment).

    Returns a list of question-ready strings that reference the figure content.
    """
    figure_type = figure_analysis.get("figure_type", "figure")
    description = figure_analysis.get("description", "")
    components = figure_analysis.get("components", [])
    concepts = figure_analysis.get("academic_concepts", [])

    questions: list[str] = []

    bloom_verb_map = {
        "L1": "List",
        "L2": "Explain",
        "L3": "Illustrate",
        "L4": "Analyze",
        "L5": "Evaluate",
        "L6": "Design",
    }
    verb = bloom_verb_map.get(bloom_level, "Explain")

    if description:
        questions.append(f"{verb} the {figure_type} shown in the figure: {description[:150]}")

    if components:
        comp_str = ", ".join(components[:4])
        questions.append(
            f"{verb} the role of the following components in the diagram: {comp_str}."
        )

    if concepts:
        concept = concepts[0] if concepts else "the concept"
        questions.append(
            f"With reference to the figure, {verb.lower()} {concept} and its significance."
        )

    return questions
