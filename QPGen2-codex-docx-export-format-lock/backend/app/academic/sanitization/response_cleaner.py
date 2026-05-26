from __future__ import annotations

import re


LEAKAGE_PATTERNS = (
    r"\bconsidering (the )?(given )?(context|uploaded academic material)\b",
    r"\bbased on (the )?(provided )?(context|material|chunks)\b",
    r"\bfrom the context\b",
    r"\bsource_indices?\s*[:=]\s*\[[^\]]*\]",
    r"```(?:json|markdown)?",
    r"```",
    # OCR / retrieval metadata artifacts
    r"\(\d+\s*marks?\s*,?\s*(?:L[1-6])?\s*,?\s*(?:Topic Outcome:?)?\s*\)",
    r"\bL[1-6]\b",
    r"\[EQUATION:[^\]]*\]",
    r"\bTopic Outcome:?\b",
    r"\bModule\s+\d+\b",
    r"\b[A-Z]{2,4}\d{3}\b",        # subject codes like BAD402
    r"---\s*Page\s+\d+\s*---",
    r"\bPage\s+\d+\b",
    r"\bProf\b\.?",
)


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


def normalize_question(text: str) -> str:
    """Normalizes capitalization, removes dangling clauses, fixes incomplete grammar/punctuation."""
    text = str(text or "").strip()
    if not text:
        return ""
        
    # Remove dangling conversational clauses at the start or end
    conversational_clauses = [
        r"\b(?:let us consider|in the example|refer to figure|here are|as shown in|alternatively)\b.*",
        r"\b(?:we can see that|consider two conclusions)\b.*"
    ]
    for clause in conversational_clauses:
        text = re.sub(clause, "", text, flags=re.IGNORECASE).strip()
        
    # Fix dangling conjunctions/prepositions at the end of the sentence
    text = re.sub(r"\b(and|or|with|in|of|is|that|to|for|at|by|from|as)\b\s*$", "", text, flags=re.IGNORECASE).strip()
    
    # Ensure it ends with a clean period or question mark
    text = text.strip(" ,-:")
    if text and not text.endswith((".", "?", "!")):
        text += "."
        
    # Fix capitalization of the first word
    if text:
        text = text[0].upper() + text[1:]
        
    # Fix double spaces
    text = re.sub(r"\s+", " ", text)
    return text


def clean_question_text(text: str) -> str:
    # First apply our LLM output repair sanitizer
    cleaned = sanitize_llm_output(text)
    
    cleaned = re.sub(r"^\s*(?:q(?:uestion)?\s*)?\d+\s*[\).:-]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*\(?[a-d]\)?\s*[\).:-]\s*", "", cleaned, flags=re.IGNORECASE)
    for pattern in LEAKAGE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\{[^{}]*(?:question|answer|source|context)[^{}]*\}", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[*_#>`]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:\n\t")
    
    # Normalize question text (capitalization, grammar, dangling clauses)
    return normalize_question(cleaned)


def validate_question_text(text: str) -> bool:
    """Strictly validates text to ensure no backend artifacts leaked and quality is publication-grade."""
    if not text:
        return False
        
    text_strip = text.strip()
    
    # Rule 1: Reject if too short (less than 6 words)
    words = text_strip.split()
    if len(words) < 6:
        return False
        
    # Rule 2: Reject if contains leaked backend/JSON tokens
    banned_tokens = ["{", "}", "Question:", "Show:", "marks", "CO", "RBT"]
    if any(b in text_strip for b in banned_tokens):
        return False
        
    # Rule 3: Reject if contains conversational fragments or figure markers
    banned_phrases = [
        "here are", "in the example", "let us consider", "figure", "alternatively", 
        "page", "advantages:", "disadvantages:", "chapter", "refer to"
    ]
    text_lower = text_strip.lower()
    if any(phrase in text_lower for phrase in banned_phrases):
        return False
        
    # Rule 4: Reject if there is a missing concept noun (e.g., "concept of with", "concept of in", "concept of and")
    missing_noun_patterns = [
        r"\bconcept of (?:with|in|and|or|of|is|that|to|for|at|by|from|as)\b",
        r"\bfeatures of In\b",
        r"\bbetween Let\b"
    ]
    if any(re.search(pat, text_strip, flags=re.IGNORECASE) for pat in missing_noun_patterns):
        return False
        
    # Rule 5: Reject if sentence is obviously cut off or grammatically incomplete
    if text_strip.endswith("..."):
        return False
        
    return True

