import re
from typing import Any

# Standard academic topics dictionary for normalization
ACADEMIC_TOPICS_DB = {
    "heuristic search": ["heuristic search", "informed search", "hill climbing", "a* search", "best first search", "heuristics"],
    "peas architecture": ["peas", "performance measure", "environment", "actuators", "sensors", "peas representation"],
    "intelligent agents": ["intelligent agent", "agent environment", "agent program", "rational agent", "structure of agents"],
    "first order logic": ["first order logic", "fol", "predicate logic", "quantifiers", "unification", "inference in fol"],
    "wumpus world": ["wumpus", "wumpus world", "knowledge-based agent", "peeking in wumpus"],
    "adversarial search": ["adversarial search", "minimax", "alpha-beta pruning", "game playing"],
    "machine learning": ["supervised", "unsupervised", "reinforcement", "neural network", "decision tree", "gradient descent"]
}

def extract_academic_topic(text: str) -> str:
    """
    Extracts a clean, normalized syllabus topic from a raw chunk text block.
    Avoids messy OCR fragments, placeholders, and sentence snippets.
    """
    text_lower = text.lower()
    
    # Try pattern matching against the academic database
    for canonical_topic, keywords in ACADEMIC_TOPICS_DB.items():
        for keyword in keywords:
            if keyword in text_lower:
                return canonical_topic.title()
                
    # Fallback: Extract the first noun-like phrase or capitalized concept
    matches = re.findall(r"\b[A-Z][a-zA-Z0-9\s-]{3,25}\b", text)
    if matches:
        # Filter out common stop-concepts
        filtered = [m.strip() for m in matches if m.lower() not in {"figure", "table", "module", "chapter", "lecture", "note"}]
        if filtered:
            return filtered[0]
            
    return "General Concept"

def extract_academic_keywords(text: str, topic: str) -> list[str]:
    """
    Extracts specific academic keywords related to the topic to enrich compiled templates.
    """
    words = re.findall(r"\b[a-zA-Z-]{4,20}\b", text.lower())
    stopwords = {"with", "that", "this", "from", "their", "under", "about", "which", "could", "would"}
    
    candidates = [w for w in words if w not in stopwords and len(w) > 3]
    unique_candidates = list(dict.fromkeys(candidates))
    
    # Return top 3 distinct keywords or fallbacks based on topic
    if len(unique_candidates) >= 2:
        return unique_candidates[:3]
    return [topic, "system architecture"]
