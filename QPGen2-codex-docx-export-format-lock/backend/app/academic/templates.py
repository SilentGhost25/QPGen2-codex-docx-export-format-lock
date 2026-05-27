"""
Deterministic VTU-Style Question Template Bank.

These templates are the CORE of the Academic Knowledge Compiler.
The LLM is NOT involved at generation time. Templates are filled
deterministically using TopicNode metadata extracted during ingestion.

Template variables:
    {topic}      — primary topic name (e.g. "A* Search Algorithm")
    {keyword}    — a specific keyword from the topic (e.g. "heuristic function")
    {keyword2}   — a second keyword for compare/contrast questions
    {module}     — module number
    {co}         — course outcome label

Each Bloom level has multiple template variants to provide diversity
across papers without any LLM inference.
"""

from __future__ import annotations

import random
import re
from typing import Any


# ---------------------------------------------------------------------------
# Template Bank — indexed by Bloom level
# ---------------------------------------------------------------------------

QUESTION_TEMPLATES: dict[str, list[str]] = {
    # L1 — Remember
    "L1": [
        "Define {topic} and state its core significance.",
        "List the key characteristics and structural features of {topic}.",
        "State the significance of {topic} in the context of {keyword}.",
        "What is {topic}? Enumerate its distinct operational characteristics.",
        "Identify and name the essential components that constitute {topic}.",
        "Outline the foundational concepts and architectural elements of {topic}.",
        "State the fundamental principles governing the operation of {topic}.",
        "Identify the main elements of {topic} and briefly state their respective functions.",
        "Enumerate the various classifications and types of {topic}.",
        "Write a structured and concise technical note on {topic}.",
    ],

    # L2 — Understand
    "L2": [
        "Explain the working principle and concept of {topic} with a suitable example.",
        "Describe the systematic working mechanism and operational workflow of {topic}.",
        "Summarize the core concept of {topic} and highlight its primary applications.",
        "Classify the different types of {topic} and explain their distinguishing features.",
        "Elucidate the functional role and significance of {keyword} in {topic}.",
        "Illustrate the block architecture and components of {topic} with a neat schematic diagram.",
        "Distinguish between the various methodological approaches employed in {topic}.",
        "Interpret the structural significance of {keyword} in the context of {topic}.",
        "Explain the comparative advantages, operational limitations, and use-cases of {topic}.",
        "Describe {topic} in detail, highlighting its operational relevance to {keyword}.",
    ],

    # L3 — Apply
    "L3": [
        "Apply the principles of {topic} to solve the given problem, detailing each step of the solution.",
        "Demonstrate the practical implementation and working of {topic} using a well-defined illustrative example.",
        "Solve the given analytical problem using {topic}, showing all intermediate steps clearly.",
        "Compute the exact output parameters using {topic} for the specified input conditions.",
        "Illustrate the practical application of {topic} in {keyword} through a worked numerical or logical example.",
        "Show how the concept of {topic} can be systematically used to determine the output for a given scenario.",
        "Apply the concept of {keyword} within {topic} to model and solve a practical engineering problem.",
        "Determine the optimal output or configuration of {topic} for the given input parameters.",
        "Using the framework of {topic}, solve the following problem and explain each analytical step.",
        "Demonstrate with a suitable scenario how {topic} effectively handles {keyword}.",
    ],

    # L4 — Analyze
    "L4": [
        "Analyze the time and space complexity of {topic} and express them in asymptotic notations.",
        "Conduct a rigorous comparative study between {topic} and {keyword}.",
        "Differentiate between the functional characteristics of {topic} and {keyword} with suitable examples.",
        "Examine the structural advantages, performance trade-offs, and design constraints of {topic}.",
        "Analyze the specific impact of {keyword} on the overall performance and throughput of {topic}.",
        "Compare and contrast {topic} and {keyword2} in terms of efficiency, scalability, and applicability.",
        "Distinguish between the execution characteristics of {topic} and {keyword} with a structured tabular comparison.",
        "Analyze and explain the behavior of {topic} under varying or extreme input conditions.",
        "Examine how the presence of {keyword} affects the correctness, stability, and efficiency of {topic}.",
        "Critically analyze the operational limitations and bottlenecks of {topic} in real-world large-scale scenarios.",
    ],

    # L5 — Evaluate
    "L5": [
        "Evaluate the performance and effectiveness of {topic} in real-world application benchmarks.",
        "Justify the adoption of {topic} over alternative methodological approaches for {keyword}.",
        "Assess the scalability and throughput of {topic} with respect to the constraints of {keyword}.",
        "Evaluate the trade-offs involved in using {topic} and recommend optimal parameter configurations.",
        "Critique the design of the approach used in {topic} and suggest structural improvements.",
        "Justify why {topic} is preferred for solving complex problems involving {keyword} with supporting technical evidence.",
        "Assess the architectural suitability of {topic} for large-scale enterprise applications.",
        "Evaluate the specific impact of {keyword} on the stability and overall performance of {topic}.",
        "Compare and evaluate the robustness of {topic} and {keyword} for practical production deployments.",
        "Defend the selection of {topic} over competing methods with strong technical and architectural arguments.",
    ],

    # L6 — Create
    "L6": [
        "Design a comprehensive solution framework using {topic} for the given problem scenario.",
        "Develop an optimized algorithm based on {topic} to solve {keyword}.",
        "Propose a novel modification to {topic} that significantly improves its time or space efficiency.",
        "Formulate an integrated approach combining the strengths of {topic} with {keyword}.",
        "Construct an architectural system design that leverages {topic} to handle {keyword}.",
        "Create a systematic, step-by-step technical procedure using {topic} to manage {keyword}.",
        "Design and implement a highly optimized, scalable version of {topic}.",
        "Plan a detailed solution architecture using {topic} to satisfy the given system requirements.",
        "Propose an architectural extension to {topic} that addresses its known scalability limitations.",
        "Develop a unified framework that seamlessly integrates {topic} with the features of {keyword}.",
    ],
}


# ---------------------------------------------------------------------------
# Image Question Templates — for questions that reference diagrams/figures
# ---------------------------------------------------------------------------

IMAGE_QUESTION_TEMPLATES: dict[str, list[str]] = {
    "L1": [
        "Identify and label the distinct components shown in the diagram related to {topic}.",
        "With reference to the given figure, enumerate the key elements and connections of {topic}.",
    ],
    "L2": [
        "Explain the fundamental concept of {topic} in detail with reference to the illustration in the given figure.",
        "Describe the systematic process flow illustrated in the diagram related to {topic}.",
        "Sketch a neat schematic diagram and explain the operational block architecture of {topic}.",
    ],
    "L3": [
        "Using the given diagram, apply the principles of {topic} and compute the final output result.",
        "With reference to the provided figure, demonstrate the step-by-step working of {topic}.",
    ],
    "L4": [
        "Analyze the state-space transition representation shown in the figure for {topic}.",
        "Analyze and compare the two alternative approaches illustrated in the diagram for {topic}.",
    ],
    "L5": [
        "Critically evaluate the correctness and efficiency of the solution shown in the figure for {topic}.",
        "Assess the architectural approach depicted in the given diagram for {topic} with respect to design standards.",
    ],
    "L6": [
        "Design an optimized and improved version of the process flow shown in the figure for {topic}.",
        "Propose systematic modifications to the system architecture depicted in the diagram for {topic}.",
    ],
}


# ---------------------------------------------------------------------------
# Marks-based suffix templates (appended to add weight to questions)
# ---------------------------------------------------------------------------

MARKS_SUFFIXES: dict[int, list[str]] = {
    2: [""],  # Short answer — no suffix needed
    3: [""],
    5: [
        "",
        " Explain with a suitable example.",
        " Illustrate with a diagram.",
    ],
    7: [
        " Explain in detail with suitable examples.",
        " Derive the necessary expressions and illustrate with an example.",
    ],
    10: [
        " Explain in detail with suitable examples and diagrams.",
        " Derive all necessary expressions, illustrate with examples, and discuss the significance.",
        " Provide a comprehensive explanation with worked examples.",
    ],
    14: [
        " Explain in detail with suitable examples and diagrams. Discuss the significance and applications.",
    ],
}


def get_marks_suffix(marks: int) -> str:
    """Get an appropriate suffix for the marks value."""
    # Find the closest marks bracket
    brackets = sorted(MARKS_SUFFIXES.keys())
    chosen = brackets[0]
    for b in brackets:
        if b <= marks:
            chosen = b
    suffixes = MARKS_SUFFIXES.get(chosen, [""])
    return random.choice(suffixes)


# ---------------------------------------------------------------------------
# Template compilation function
# ---------------------------------------------------------------------------

BAD_PHRASES = [
    "topic outcome",
    "from the perspective of",
    "as discussed in",
    "in relation to",
    "with references to the text",
    "fundamental concepts",
]

QUESTION_INTENTS = {
    "L1": ["Define", "List", "Identify"],
    "L2": ["Explain", "Describe", "Summarize"],
    "L3": ["Apply", "Demonstrate", "Solve"],
    "L4": ["Analyze", "Differentiate", "Compare"],
    "L5": ["Evaluate", "Critique", "Justify"],
    "L6": ["Design", "Develop", "Propose"]
}

def sanitize_and_normalize_question(text: str, bloom_level: str, topic: str = "") -> str:
    """
    Sanitize question text by blacklisting LLM fluff/OCR artifacts, enforcing precise
    academic Bloom verbs, and clamping length to max 18 words for true direct VTU style.
    """
    # 1. Clean bad phrases
    for phrase in BAD_PHRASES:
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)

    # Clean double spaces/stray grammar marks
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?])", r"\1", text)

    # 2. Map precise academic intents
    level = bloom_level.strip().upper()
    intents = QUESTION_INTENTS.get(level, ["Explain"])
    
    words = text.split()
    if words:
        first_word = words[0].rstrip(",.:;!?")
        # If the first word is a generic verb or not in the specific intent category,
        # we map it to the primary intent verb for that level.
        generic_verbs = {"discuss", "explain", "describe", "analyze", "evaluate", "critique", "design", "develop", "define", "list"}
        if first_word.lower() in generic_verbs:
            target_intent = intents[0]
            if first_word.lower() != target_intent.lower():
                words[0] = target_intent
                text = " ".join(words)

    # 3. Clamp word length to max 18 words (direct VTU style)
    words = text.split()
    if len(words) > 18:
        text = " ".join(words[:18])
        if not text.endswith(".") and not text.endswith("?"):
            text += "."
            
    return text.strip()

def compile_question(
    topic: str,
    bloom_level: str,
    keywords: list[str] | None = None,
    marks: int = 5,
    is_image_question: bool = False,
    used_templates: set[int] | None = None,
) -> str:
    """
    Compile a single question deterministically from templates.

    Args:
        topic: The topic name (e.g. "Binary Search Tree").
        bloom_level: Bloom level string like "L1", "L2", etc.
        keywords: List of keywords from the TopicNode.
        marks: Marks for the question.
        is_image_question: Whether this is an image-based question.
        used_templates: Set of already-used template indices for dedup.

    Returns:
        A fully formed question string.
    """
    if used_templates is None:
        used_templates = set()

    level = bloom_level.strip().upper()
    if level not in QUESTION_TEMPLATES:
        level = "L2"  # Safe fallback

    # Choose template bank
    if is_image_question and level in IMAGE_QUESTION_TEMPLATES:
        bank = IMAGE_QUESTION_TEMPLATES[level]
    else:
        bank = QUESTION_TEMPLATES[level]

    # Pick a template that hasn't been used yet
    available = [(i, t) for i, t in enumerate(bank) if i not in used_templates]
    if not available:
        # All used — reset and allow reuse
        available = list(enumerate(bank))

    idx, template = random.choice(available)
    used_templates.add(idx)

    # Prepare keywords
    kw = keywords or []
    keyword = kw[0] if len(kw) > 0 else topic
    keyword2 = kw[1] if len(kw) > 1 else keyword

    # Fill template
    question = template.format(
        topic=topic,
        keyword=keyword,
        keyword2=keyword2,
        module="",
        co="",
    )

    # Add marks-appropriate suffix
    suffix = get_marks_suffix(marks)
    if suffix and not question.endswith("."):
        question = question.rstrip(".") + "." + suffix
    elif suffix:
        question = question + suffix

    compiled = question.strip()
    return sanitize_and_normalize_question(compiled, level, topic)
