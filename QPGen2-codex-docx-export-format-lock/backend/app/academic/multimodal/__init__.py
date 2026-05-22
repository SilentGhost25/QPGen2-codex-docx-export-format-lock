"""
Multimodal Document Parsing Package.

Provides structured visual understanding for academic documents:
  PDF/DOCX/Image → Layout Detection → Specialized Extractors → Structured JSON

Components:
  - pdf_extractor:     Extract embedded images from PDFs (PyMuPDF)
  - layout_parser:     Detect block types (text, heading, table, equation, figure)
  - math_extractor:    Formula/equation OCR via vision LLM
  - figure_analyzer:   Diagram/figure understanding via vision LLM
  - structured_parser: Orchestrator — produces per-page structured JSON
"""

from .structured_parser import parse_document_structure, StructuredDocument, PageBlock

__all__ = ["parse_document_structure", "StructuredDocument", "PageBlock"]
