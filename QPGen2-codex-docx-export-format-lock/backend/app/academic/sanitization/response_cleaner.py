from __future__ import annotations

import re


LEAKAGE_PATTERNS = (
    r"\bconsidering (the )?(given )?(context|uploaded academic material)\b",
    r"\bbased on (the )?(provided )?(context|material|chunks)\b",
    r"\bfrom the context\b",
    r"\bsource_indices?\s*[:=]\s*\[[^\]]*\]",
    r"```(?:json|markdown)?",
    r"```",
)


def clean_question_text(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^\s*(?:q(?:uestion)?\s*)?\d+\s*[\).:-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*\(?[a-d]\)?\s*[\).:-]\s*", "", cleaned, flags=re.IGNORECASE)
    for pattern in LEAKAGE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\{[^{}]*(?:question|answer|source|context)[^{}]*\}", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[*_#>`]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:\n\t")
    return cleaned
