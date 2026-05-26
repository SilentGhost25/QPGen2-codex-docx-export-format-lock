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
from typing import Any


# ---------------------------------------------------------------------------
# Template Bank — indexed by Bloom level
# ---------------------------------------------------------------------------

QUESTION_TEMPLATES: dict[str, list[str]] = {
    # L1 — Remember
    "L1": [
        "Define {topic}.",
        "List the key features of {topic}.",
        "State the significance of {topic} in the context of {keyword}.",
        "What is {topic}? Mention its characteristics.",
        "Name the components of {topic}.",
        "Outline the basic concepts of {topic}.",
        "Recall the fundamental principles of {topic}.",
        "Identify the main elements of {topic}.",
        "Enumerate the types of {topic}.",
        "Write a short note on {topic}.",
    ],

    # L2 — Understand
    "L2": [
        "Explain {topic} with a suitable example.",
        "Describe the working principle of {topic}.",
        "Summarize the concept of {topic} and its applications.",
        "Classify the different types of {topic}.",
        "Discuss the role of {keyword} in {topic}.",
        "Illustrate {topic} with a neat diagram.",
        "Distinguish between the various approaches used in {topic}.",
        "Interpret the significance of {keyword} in the context of {topic}.",
        "Explain the advantages and limitations of {topic}.",
        "Describe {topic} and its relevance to {keyword}.",
    ],

    # L3 — Apply
    "L3": [
        "Apply {topic} to solve a suitable problem and show the steps involved.",
        "Demonstrate the working of {topic} with an example.",
        "Solve a problem using {topic}. Show all intermediate steps.",
        "Compute the result using {topic} for a given input.",
        "Illustrate the application of {topic} in {keyword} with a worked example.",
        "Show how {topic} can be used to determine the output for a given scenario.",
        "Apply the concept of {keyword} in {topic} to a practical problem.",
        "Determine the output of {topic} for the given input parameters.",
        "Using {topic}, solve the following and explain each step.",
        "Demonstrate with an example how {topic} handles {keyword}.",
    ],

    # L4 — Analyze
    "L4": [
        "Analyze the time and space complexity of {topic}.",
        "Compare and contrast {topic} with {keyword}.",
        "Differentiate between {topic} and {keyword} with suitable examples.",
        "Examine the advantages and disadvantages of {topic}.",
        "Analyze the role of {keyword} in the performance of {topic}.",
        "Compare {topic} and {keyword2} in terms of efficiency and applicability.",
        "Distinguish between {topic} and {keyword} with a tabular comparison.",
        "Analyze the behavior of {topic} under different input conditions.",
        "Examine how {keyword} affects the correctness of {topic}.",
        "Critically analyze the limitations of {topic} in real-world scenarios.",
    ],

    # L5 — Evaluate
    "L5": [
        "Evaluate the effectiveness of {topic} in real-world applications.",
        "Justify the use of {topic} over alternative approaches for {keyword}.",
        "Assess the performance of {topic} with respect to {keyword}.",
        "Evaluate the trade-offs involved in using {topic}.",
        "Critique the approach used in {topic} and suggest improvements.",
        "Justify why {topic} is preferred for solving problems involving {keyword}.",
        "Assess the suitability of {topic} for large-scale applications.",
        "Evaluate the impact of {keyword} on the overall performance of {topic}.",
        "Compare and evaluate {topic} and {keyword} for practical applications.",
        "Defend the choice of {topic} over other methods with supporting arguments.",
    ],

    # L6 — Create
    "L6": [
        "Design a solution using {topic} for the given problem scenario.",
        "Develop an algorithm based on {topic} to solve {keyword}.",
        "Propose a modification to {topic} that improves its efficiency.",
        "Formulate a new approach combining {topic} with {keyword}.",
        "Construct a system that leverages {topic} for {keyword}.",
        "Create a step-by-step procedure using {topic} to handle {keyword}.",
        "Design and implement an optimized version of {topic}.",
        "Plan a solution architecture using {topic} for the given requirements.",
        "Propose an extension to {topic} that addresses its known limitations.",
        "Develop a framework that integrates {topic} with {keyword}.",
    ],
}


# ---------------------------------------------------------------------------
# Image Question Templates — for questions that reference diagrams/figures
# ---------------------------------------------------------------------------

IMAGE_QUESTION_TEMPLATES: dict[str, list[str]] = {
    "L1": [
        "Identify the components shown in the diagram related to {topic}.",
        "With reference to the given figure, list the elements of {topic}.",
    ],
    "L2": [
        "Explain the concept of {topic} with reference to the given figure.",
        "Describe the process illustrated in the diagram related to {topic}.",
        "With a neat diagram, explain {topic}.",
    ],
    "L3": [
        "Using the given diagram, apply {topic} and determine the result.",
        "With reference to the figure, demonstrate the working of {topic}.",
    ],
    "L4": [
        "Analyze the state-space representation shown in the figure for {topic}.",
        "Compare the two approaches illustrated in the diagram for {topic}.",
    ],
    "L5": [
        "Evaluate the correctness of the solution shown in the figure for {topic}.",
        "Assess the approach depicted in the given diagram for {topic}.",
    ],
    "L6": [
        "Design an improved version of the process shown in the figure for {topic}.",
        "Propose modifications to the architecture depicted in the diagram for {topic}.",
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

    return question.strip()
