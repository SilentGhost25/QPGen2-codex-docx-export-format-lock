"""
Academic Policies and Enforcements.

Provides deterministic validation and mappings for COs, Bloom's levels (RBT), and Action Verbs
to ensure perfect pedagogical alignment without relying on LLM behavior.
"""

from typing import Any

# Global Course Outcome (CO) to Revised Bloom's Taxonomy (RBT) allowed levels policy
CO_RBT_POLICY = {
    "CO1": ["L1", "L2"],
    "CO2": ["L3"],
    "CO3": ["L4"],
    "CO4": ["L5"],
    "CO5": ["L6"],
}

RBT_DIFFICULTY_POLICY = {
    "L1": "easy",
    "L2": "easy",
    "L3": "medium",
    "L4": "medium",
    "L5": "hard",
    "L6": "hard",
}

# Standard Bloom's levels action verbs for engineering/technical curricula (e.g., VTU)
RBT_VERBS = {
    "L1": ["Define", "List", "State", "Recall", "Identify", "Name", "Outline"],
    "L2": ["Explain", "Describe", "Summarize", "Classify", "Discuss", "Illustrate"],
    "L3": ["Apply", "Demonstrate", "Solve", "Calculate", "Compute", "Show", "Determine"],
    "L4": ["Analyze", "Compare", "Differentiate", "Contrast", "Distinguish", "Examine"],
    "L5": ["Evaluate", "Critique", "Justify", "Assess", "Compare", "Defend"],
    "L6": ["Design", "Create", "Develop", "Formulate", "Construct", "Plan", "Propose"],
}

def get_allowed_rbt(co: str) -> list[str]:
    """Get allowed Bloom levels for a given CO (default L1/L2 if missing)."""
    clean_co = co.strip().upper()
    # Support forms like "CO1", "CO-1", "COURSE OUTCOME 1"
    for key in CO_RBT_POLICY:
        if key in clean_co:
            return CO_RBT_POLICY[key]
    return ["L1", "L2"]


def derive_rbt_for_co(co: str, *, slot_index: int = 0) -> str:
    """Return the deterministic backend-owned RBT for a CO."""
    allowed = get_allowed_rbt(co)
    return allowed[slot_index % len(allowed)]


def derive_difficulty_for_rbt(rbt: str) -> str:
    """Difficulty is backend policy, never frontend authority."""
    return RBT_DIFFICULTY_POLICY.get(rbt.strip().upper(), "medium")

def validate_co_rbt_alignment(co: str, rbt: str) -> bool:
    """Deterministically checks if the RBT level is academically valid for the targeted CO."""
    clean_co = co.strip().upper()
    clean_rbt = rbt.strip().upper()
    # Map back to standard CO keys
    matched_key = None
    for key in CO_RBT_POLICY:
        if key in clean_co:
            matched_key = key
            break
    if not matched_key:
        return True # Fallback if CO structure is non-standard
    
    return clean_rbt in CO_RBT_POLICY[matched_key]

def has_rbt_action_verb(text: str, rbt: str) -> bool:
    """Checks if the question text contains or starts with expected action verbs for the RBT level."""
    clean_text = text.strip().lower()
    clean_rbt = rbt.strip().upper()
    verbs = RBT_VERBS.get(clean_rbt, [])
    if not verbs:
        return True
    
    # Check if the question starts with or prominently contains any of the action verbs
    for verb in verbs:
        v_low = verb.lower()
        # Checks if verb is at the start or follows a common prefix (e.g., "Q1. Explain...", "Explain...")
        if clean_text.startswith(v_low) or f" {v_low} " in clean_text or f"\n{v_low} " in clean_text:
            return True
    return False
