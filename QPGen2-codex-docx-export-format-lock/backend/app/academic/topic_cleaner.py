"""
Topic Cleaner and Academic Subject Vocabulary Mapper.

Cleans noisy heading/OCR fragments and maps topics/keywords to verified academic concepts.
"""

from __future__ import annotations

import re

BAD_PATTERNS = [
    r"Here are two commonly used candidates",
    r"Let us consider",
    r"In the example",
    r"Figure \d+",
    r"Advantages:",
    r"Alternatively",
    r"with a predetermined depth limit P",
    r"nodes at depth E are treated",
    r"let us consider two possible conclusions",
    r"in the example",
    r"we can see that",
    r"as shown in",
    r"refer to",
    r"see section",
    r"for example",
    r"such that",
    r"with respect to",
    r"on the other hand",
]

VALID_TOPICS = [
    "Artificial Intelligence",
    "A* Search",
    "Breadth First Search",
    "Depth First Search",
    "Depth Limited Search",
    "Iterative Deepening Search",
    "Heuristic Functions",
    "Wumpus World",
    "PEAS Description",
    "State Space Search",
    "Alpha-Beta Pruning",
    "Minimax Algorithm",
    "Knowledge Representation",
    "First Order Logic",
    "Propositional Logic",
    "Inference in First Order Logic",
    "Forward Chaining",
    "Backward Chaining",
    "Unification and Resolution",
    "Bayes Theorem",
    "Bayesian Networks",
    "Probabilistic Reasoning",
    "Machine Learning",
    "Supervised Learning",
    "Unsupervised Learning",
    "Reinforcement Learning",
    "Neural Networks",
    "Deep Learning",
    "Natural Language Processing",
    "Computer Vision",
    "Robotics",
    "Expert Systems",
    "Constraint Satisfaction Problems",
    "Backtracking Search",
    "Genetic Algorithms",
    "Hill Climbing Search",
    "Simulated Annealing",
    "Greedy Best First Search",
]


def clean_topic(text: str) -> str:
    """Strip out grammatical noise, conversational phrases, and OCR artifacts."""
    if not text:
        return ""
    
    # Strip figure paths/seals if present
    text = re.sub(r"\[(?:FIGURE|FIG|EQUATION):[^\]]*\]", "", text, flags=re.IGNORECASE)
    
    # Remove BAD_PATTERNS case-insensitively
    for pattern in BAD_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
        
    # Clean up double punctuation or spaces
    text = re.sub(r"[^\w\s\.*-]", "", text)
    text = re.sub(r"\s+", " ", text)
    text = text.strip()
    
    # Capitalize first letter of each word to look professional
    return " ".join([w.capitalize() for w in text.split()])


def get_jaccard_similarity(str1: str, str2: str) -> float:
    """Calculate word token overlap Jaccard similarity, ignoring stopwords."""
    from .topic_graph import STOPWORDS
    words1 = set(re.findall(r"\w+", str1.lower()))
    words2 = set(re.findall(r"\w+", str2.lower()))
    
    words1 = words1 - STOPWORDS
    words2 = words2 - STOPWORDS
    
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def map_to_nearest_valid_topic(topic_name: str) -> str:
    """
    Maps any noisy heading or chunk title to the nearest valid academic topic.
    Returns clean original if no high-confidence match is found.
    """
    clean_name = clean_topic(topic_name)
    if not clean_name or len(clean_name.split()) < 2:
        # Avoid maps for single simple words, unless it matches standard topics
        if clean_name.lower() in [t.lower() for t in VALID_TOPICS]:
            return next(t for t in VALID_TOPICS if t.lower() == clean_name.lower())
        return clean_name or "General Concepts"

    # 1. Jaccard similarity check (very fast and highly reliable for token overlap)
    best_jaccard = 0.0
    best_jaccard_topic = None
    
    for vt in VALID_TOPICS:
        sim = get_jaccard_similarity(clean_name, vt)
        if sim > best_jaccard:
            best_jaccard = sim
            best_jaccard_topic = vt
            
    if best_jaccard >= 0.35 and best_jaccard_topic:
        return best_jaccard_topic

    # 2. Substring matching
    for vt in VALID_TOPICS:
        if vt.lower() in clean_name.lower() or clean_name.lower() in vt.lower():
            return vt

    # 3. Embedding-based fallback
    try:
        from .embeddings import generate_embedding, cosine_similarity
        q_emb = generate_embedding(clean_name)
        if q_emb:
            best_sim = 0.0
            best_topic = None
            for vt in VALID_TOPICS:
                vt_emb = generate_embedding(vt)
                if vt_emb:
                    sim = cosine_similarity(q_emb, vt_emb)
                    if sim > best_sim:
                        best_sim = sim
                        best_topic = vt
            if best_sim >= 0.60 and best_topic:
                return best_topic
    except Exception:
        pass

    return clean_name


_kw_model = None

def extract_keybert_keywords(text: str) -> list[str]:
    """Extract high-quality keywords using KeyBERT if installed, fallback to empty list."""
    global _kw_model
    try:
        from keybert import KeyBERT
        if _kw_model is None:
            # Load KeyBERT model lazily
            _kw_model = KeyBERT()
        keywords = _kw_model.extract_keywords(text, top_n=5)
        return [kw[0].title() for kw in keywords]
    except Exception:
        return []
