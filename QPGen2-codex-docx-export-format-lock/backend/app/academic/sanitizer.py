"""
Output Sanitation Layer for Exam Questions.

Ensures that exported question texts are perfectly clean and professional, free of
internal metadata, marks tags, Bloom level annotations, and chain-of-thought traces.
"""

import re

REMOVE_PATTERNS = [
    r"Thought Process:.*?(?=\n\n|\Z)",
    r"Reasoning:.*?(?=\n\n|\Z)",
    r"Explanation:.*?(?=\n\n|\Z)",
    r"Assessment Objectives:.*?(?=\n\n|\Z)",
    r"CO Mapping:.*?(?=\n|\Z)",
    r"CO\d.*?(?=\n|\Z)",
    r"RBT.*?(?=\n|\Z)",
    r"Bloom.*?(?=\n|\Z)",
    r"Module:.*?(?=\n|\Z)",
    r"Difficulty:.*?(?=\n|\Z)",
    r"Marks:.*?(?=\n|\Z)",
    r"Page Formatting:.*?(?=\n\n|\Z)",
    r"###.*?###",
    r"\*\*.*?\*\*",
]

# Patterns that represent artifact content that leaked from chunk text into questions
ARTIFACT_PATTERNS = [
    r"---\s*Page\s*\d+\s*---",           # --- Page 1 ---
    r"\[EQUATION:[^\]]*\]",               # [EQUATION: ...]
    r"\[FIGURE:[^\]]*\]",                 # [FIGURE: ...]
    r"\[TABLE:[^\]]*\]",                  # [TABLE: ...]
    r"\[IMAGE:[^\]]*\]",                  # [IMAGE: ...]
    r"in the context of.*?(?=\n|$)",      # leaked fallback phrase
    r"considering.*?(?=\n|$)",            # leaked fallback phrase
    r"with reference to.*?(?=\n|$)",      # leaked source reference
    r"uploaded academic material.*?(?=\n|$)",
    r"Here are two commonly used candidates:.*?(?=\n|$)",
    r"The steps are as follows:.*?(?=\n|$)",
    r"mutually exclusive and exhaustive.*?(?=\n|$)",
    r"\[FIGUR.*?(?=\n|$)",
    r"Module\s*-\s*\d+",
]


def sanitize_llm_output(text: str) -> str:
    """Repairs and sanitizes LLM output containing leaked backend artifacts or JSON brackets."""
    text = str(text or "").strip()
    # Remove curly braces and JSON-like/Python-dict prefixes (e.g. {"Question": "foo"} -> "foo")
    text = re.sub(r"\{.*?:", "", text)
    text = text.replace("}", "")
    text = text.replace('"', "")
    text = text.replace("'", "")
    
    # Strip common prefix labels
    prefixes = [
        "Question:", "question:", "QUESTION:",
        "Show:", "show:", "SHOW:",
        "Explain:", "explain:", "EXPLAIN:"
    ]
    for pref in prefixes:
        if text.startswith(pref):
            text = text[len(pref):].strip()
            
    return text.strip()


def sanitize_question_output(text: str) -> str:
    """
    Cleans a question text by stripping out reasoning traces, assessment goals,
    page markers, and metadata lines to leave ONLY the final pure question text.
    """
    if not text:
        return ""
        
    cleaned = sanitize_llm_output(text)
    
    # Strip common markdown bold prefix formatting if the model wrapped tags
    # e.g., "**Question:** Explain..." -> "Explain..."
    cleaned = re.sub(r"^\s*\**Question\**:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*\**Q\d+\**:\s*", "", cleaned, flags=re.IGNORECASE)

    # Remove artifact content (page markers, visual element tags) that leaked from chunk text
    for pattern in ARTIFACT_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Apply all remove patterns
    for pattern in REMOVE_PATTERNS:
        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL
        )
        
    # Strip any markdown bold asterisks surrounding the entire text or starts/ends of lines
    cleaned = re.sub(r"\*\*+", "", cleaned)
    cleaned = re.sub(r"^\s*-\s*", "", cleaned)
    
    # Remove any trailing junk or empty brackets that got left behind
    cleaned = re.sub(r"\s*[\(\[]\s*[\)\]]\s*$", "", cleaned)
    
    # Clean up excess newlines (3 or more) to at most 2
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    
    # Normalize multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    
    cleaned = cleaned.strip()

    # Repair question (enforce trailing punctuation if missing)
    if cleaned and not cleaned[-1] in ".?!":
        # Check if the sentence has basic question keywords
        lower_q = cleaned.lower()
        if lower_q.startswith(("what", "why", "how", "when", "where", "which", "who", "is", "are", "do", "does", "can", "could", "would")):
            cleaned += "?"
        else:
            cleaned += "."
    
    return cleaned

