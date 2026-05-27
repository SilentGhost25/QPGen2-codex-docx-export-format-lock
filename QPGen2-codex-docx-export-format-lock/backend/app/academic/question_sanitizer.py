import re

BAD_PATTERNS = [
    "Topic Outcome",
    "from the perspective of",
    "with references to the text",
    "as discussed in",
    "(.",
    "topic outcome",
    "syllabus concepts",
    "fundamental concepts",
    "module outcome",
]

QUALITY_REJECT_PATTERNS = [
    "Topic Outcome",
    "fundamental concepts",
    "from the perspective",
]

def sanitize_question(text: str) -> str:
    if not text:
        return ""
    for p in BAD_PATTERNS:
        text = text.replace(p, "")
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    if text.endswith("("):
        text = text[:-1]
    if text.endswith("(."):
        text = text[:-2]
    return text.strip()

def is_quality_rejected(text: str) -> bool:
    lower = text.lower()
    for p in QUALITY_REJECT_PATTERNS:
        if p.lower() in lower:
            return True
    return False
