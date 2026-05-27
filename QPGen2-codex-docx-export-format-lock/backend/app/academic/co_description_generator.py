import logging
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models import Subject
from app.academic.models import KnowledgeChunk, SubjectSyllabus

logger = logging.getLogger("app.academic.co_description_generator")

def format_topics_list(topics: list[str]) -> str:
    """Formats a list of topics into a grammatically correct string."""
    if not topics:
        return "relevant academic concepts"
        
    # Deduplicate while preserving order
    unique_topics = []
    for t in topics:
        clean = t.strip()
        if clean and clean not in unique_topics:
            unique_topics.append(clean)
            
    unique_topics = unique_topics[:4]  # limit to top 4 topics for readability
    
    if not unique_topics:
        return "relevant academic concepts"
    if len(unique_topics) == 1:
        return unique_topics[0]
    elif len(unique_topics) == 2:
        return f"{unique_topics[0]} and {unique_topics[1]}"
    else:
        return ", ".join(unique_topics[:-1]) + f", and {unique_topics[-1]}"

def generate_subject_co_descriptions(db: Session, subject_id: int) -> dict[str, str]:
    """
    Synthesizes and saves Course Outcome (CO) descriptions dynamically from module chunks.
    Respects subject-specific styles and keeps the syllabus aligned automatically.
    """
    subject = db.scalar(select(Subject).where(Subject.id == subject_id))
    if not subject:
        logger.warning(f"Subject with ID {subject_id} not found.")
        return {}

    # Query all KnowledgeChunks for the subject
    chunks = list(db.scalars(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.subject_id == subject_id)
        .order_by(KnowledgeChunk.module_number, KnowledgeChunk.id)
    ))

    # Group topics by module
    module_topics = {}
    for chunk in chunks:
        mod = chunk.module_number or 1
        if mod not in module_topics:
            module_topics[mod] = []
        topic = chunk.topic_name
        if topic and topic.strip() and topic.lower() not in {"figure", "table", "general concept", "concept"}:
            if topic.strip() not in module_topics[mod]:
                module_topics[mod].append(topic.strip())

    # Fallback to SubjectSyllabus modules if chunk topics are sparse
    syllabus = db.scalar(select(SubjectSyllabus).where(SubjectSyllabus.subject_id == subject_id))
    if syllabus and syllabus.modules_json:
        for mod_data in syllabus.modules_json:
            mod = mod_data.get("module") or 1
            topics = mod_data.get("topics") or []
            if mod not in module_topics or not module_topics[mod]:
                module_topics[mod] = [t.strip() for t in topics if t]

    # Detect subject style
    subj_name = (subject.name or "").lower()
    subj_code = (subject.code or "").lower()

    is_os = "operating system" in subj_name or "os" in subj_code or "operating-system" in subj_name
    is_ai = any(term in subj_name for term in ["artificial intelligence", "machine learning", "neural", "deep learning", "ai", "ml"])

    # Define subject-specific templates
    CO_TEMPLATES_AI = {
        "CO1": "Explain the fundamental concepts, philosophy, and intelligent agent architectures of {topics} in Artificial Intelligence.",
        "CO2": "Apply search strategies and problem-solving techniques of {topics} in Artificial Intelligence systems.",
        "CO3": "Analyze heuristic search methods, knowledge representation, and reasoning techniques used in {topics}.",
        "CO4": "Evaluate logic-based reasoning and uncertainty handling approaches in {topics} applications.",
        "CO5": "Develop intelligent solutions using Artificial Intelligence concepts, machine learning, and decision-making techniques related to {topics}.",
    }

    CO_TEMPLATES_OS = {
        "CO1": "Explain the fundamental structure, processes, and CPU scheduling algorithms of {topics} in Operating Systems.",
        "CO2": "Apply memory management, paging, and virtual memory allocation techniques of {topics}.",
        "CO3": "Analyze process synchronization, concurrency controls, and deadlock handling strategies used in {topics}.",
        "CO4": "Evaluate the performance, limitations, and structures of storage and file systems in {topics}.",
        "CO5": "Develop systems programming solutions and security policies based on concepts of {topics}.",
    }

    CO_TEMPLATES_DEFAULT = {
        "CO1": "Explain the fundamental concepts, theories, and models of {topics}.",
        "CO2": "Apply the principles and operational methods of {topics} to solve domain-specific problems.",
        "CO3": "Analyze the methodologies, structural designs, and execution workflows used in {topics}.",
        "CO4": "Evaluate the effectiveness, performance characteristics, and constraints of {topics} in engineering applications.",
        "CO5": "Develop optimal implementations, designs, and integrated solutions using concepts related to {topics}.",
    }

    if is_ai:
        templates = CO_TEMPLATES_AI
    elif is_os:
        templates = CO_TEMPLATES_OS
    else:
        templates = CO_TEMPLATES_DEFAULT

    co_descriptions = {}
    for i in range(1, 6):
        co_key = f"CO{i}"
        topics = module_topics.get(i, [])
        if not topics:
            # General fallback if no topics were found in module
            fallback_topics = [subject.name or "subject modules"]
            topics_str = format_topics_list(fallback_topics)
        else:
            topics_str = format_topics_list(topics)
            
        template = templates.get(co_key, CO_TEMPLATES_DEFAULT[co_key])
        co_descriptions[co_key] = template.format(topics=topics_str)

    # Save to database
    if syllabus:
        if syllabus.co_json:
            # Overwrite or merge
            syllabus.co_json = {**syllabus.co_json, **co_descriptions}
        else:
            syllabus.co_json = co_descriptions
        db.commit()
        logger.info(f"Updated CO descriptions for subject ID {subject_id}: {co_descriptions}")
    else:
        syllabus = SubjectSyllabus(
            subject_id=subject_id,
            co_json=co_descriptions,
            modules_json=[]
        )
        db.add(syllabus)
        db.commit()
        logger.info(f"Created new SubjectSyllabus with CO descriptions for subject ID {subject_id}: {co_descriptions}")

    return co_descriptions
