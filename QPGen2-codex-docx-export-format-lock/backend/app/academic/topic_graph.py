"""
Knowledge Graph Builder for the Academic Question Compiler.

This module parses KnowledgeChunk records from the database and groups them
into high-fidelity TopicNode objects (the "Knowledge Graph") representing
the curriculum. It extracts rich academic keywords and links images to topics.
"""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import KnowledgeChunk

logger = logging.getLogger("app.academic.topic_graph")

# Common English and academic stopwords to ignore when extracting keywords
STOPWORDS = {
    "the", "and", "a", "of", "to", "in", "is", "that", "it", "for", "on", "with", "as", "this", "its", "are", "by", 
    "an", "be", "from", "at", "or", "which", "also", "has", "have", "can", "will", "show", "given", "using", "used", 
    "explain", "describe", "define", "solve", "calculate", "analyze", "evaluate", "design", "illustrate", "discuss",
    "working", "neat", "diagram", "figure", "table", "caption", "description", "module", "subject", "chapter", "unit",
    "question", "marks", "bloom", "taxonomy", "level", "course", "outcome", "mapping", "concept", "principle", 
    "features", "characteristics", "significance", "types", "different", "various", "elements", "components", "context",
    "what", "how", "why", "where", "when", "who", "which", "whom", "whose", "then", "than", "there", "their", "them",
    "about", "above", "after", "again", "against", "all", "am", "any", "but", "if", "into", "no", "nor", "not", "only",
    "our", "ours", "out", "over", "same", "so", "some", "such", "too", "very", "was", "were", "been", "being"
}


@dataclass
class TopicNode:
    """A high-fidelity structured concept node in the Subject's Knowledge Graph."""
    module: int
    topic: str
    keywords: list[str] = field(default_factory=list)
    co: str = "CO1"
    bloom_level: str = "L2"
    image_path: str | None = None
    content_summary: str = ""
    chunk_ids: list[int] = field(default_factory=list)  # IDs of source KnowledgeChunks


def extract_keywords_from_text(text: str) -> list[str]:
    """
    Extract high-quality academic keywords/phrases from text deterministically
    without external NLP dependencies.
    """
    keywords = set()
    
    # 1. Bolded text: **word/phrase**
    for match in re.findall(r"\*\*(.*?)\*\*", text):
        cleaned = re.sub(r"[^\w\s-]", "", match).strip()
        if cleaned and len(cleaned) > 2 and cleaned.lower() not in STOPWORDS:
            keywords.add(cleaned)
            
    # 2. Code blocks: `code`
    for match in re.findall(r"`(.*?)`", text):
        cleaned = re.sub(r"[^\w\s\.-]", "", match).strip()
        if cleaned and len(cleaned) > 2 and cleaned.lower() not in STOPWORDS:
            keywords.add(cleaned)
            
    # 3. Capitalized phrases (e.g., "A* Search", "Binary Search Tree", "TCP/IP")
    # Finds consecutive words starting with a capital letter
    for match in re.findall(r"\b([A-Z][a-zA-Z0-9*-]*(?:\s+[A-Z][a-zA-Z0-9*-]*){0,2})\b", text):
        cleaned = match.strip()
        if cleaned and len(cleaned) > 2 and cleaned.lower() not in STOPWORDS:
            keywords.add(cleaned)
            
    # 4. Fallback: standard word frequency
    words = re.findall(r"\b[a-zA-Z]{4,20}\b", text.lower())
    filtered_words = [w for w in words if w not in STOPWORDS]
    word_counts = Counter(filtered_words)
    for w, count in word_counts.most_common(5):
        keywords.add(w.title())
        
    return sorted(list(keywords))[:10]


def build_topic_graph(
    db: Session,
    subject_id: int,
    module_filter: int | None = None
) -> list[TopicNode]:
    """
    Queries the KnowledgeChunk database table for a given subject and groups them
    into structured TopicNode objects.
    """
    stmt = select(KnowledgeChunk).where(KnowledgeChunk.subject_id == subject_id)
    if module_filter is not None:
        stmt = stmt.where(KnowledgeChunk.module_number == module_filter)
        
    chunks = db.scalars(stmt).all()
    if not chunks:
        logger.warning(f"No knowledge chunks found for subject_id {subject_id}")
        return []

    from .topic_cleaner import map_to_nearest_valid_topic
    
    # Group chunks by normalized topic name and module
    grouped_chunks = defaultdict(list)
    for chunk in chunks:
        mod = chunk.module_number if chunk.module_number is not None else 1
        topic = chunk.topic_name if chunk.topic_name else "General Concepts"
        
        # Clean topic name using academic cleaner and vocabulary mapper
        clean_topic = map_to_nearest_valid_topic(topic)
            
        grouped_chunks[(mod, clean_topic)].append(chunk)

    topic_nodes = []
    
    for (module, topic_name), topic_chunks in grouped_chunks.items():
        # 1. Infer most frequent Course Outcome and Bloom Level for this topic
        cos = [c.co_mapping for c in topic_chunks if c.co_mapping]
        blooms = [c.bloom_level for c in topic_chunks if c.bloom_level]
        
        co = Counter(cos).most_common(1)[0][0] if cos else "CO1"
        bloom = Counter(blooms).most_common(1)[0][0] if blooms else "L2"
        
        # 2. Extract keywords from all chunks for this topic
        all_keywords = set()
        image_path = None
        combined_text = ""
        
        for c in topic_chunks:
            combined_text += c.chunk_text + "\n"
            
            # Extract image path if this chunk represents a figure or contains figure references
            if "[FIGURE_PATH:" in c.chunk_text:
                img_match = re.search(r"\[FIGURE_PATH:\s*([^\]]+)\]", c.chunk_text)
                if img_match:
                    image_path = img_match.group(1).strip()
            
            # Extract keywords from individual chunk text and summary
            keywords_text = c.chunk_text
            if c.chunk_summary:
                keywords_text += "\n" + c.chunk_summary
            
            # Extract using KeyBERT if available, else fallback to standard deterministic extractor
            from .topic_cleaner import extract_keybert_keywords
            kb_kws = extract_keybert_keywords(keywords_text)
            if kb_kws:
                all_keywords.update(kb_kws)
            else:
                all_keywords.update(extract_keywords_from_text(keywords_text))

        # 3. Create TopicNode
        node = TopicNode(
            module=module,
            topic=topic_name,
            keywords=sorted(list(all_keywords))[:8],
            co=co,
            bloom_level=bloom,
            image_path=image_path,
            content_summary=combined_text[:300].strip() + "...",
            chunk_ids=[c.id for c in topic_chunks if c.id is not None],
        )
        topic_nodes.append(node)

    logger.info(f"Built Topic Graph with {len(topic_nodes)} nodes for subject_id {subject_id}")
    return topic_nodes
