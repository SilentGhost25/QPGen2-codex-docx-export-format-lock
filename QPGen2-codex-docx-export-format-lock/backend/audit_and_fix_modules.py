import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
# Import ALL models from core and academic to register them in metadata registry
from app.models import User, Subject, Department, QuestionPaper, PaperQuestion, Question
from app.academic.models import AcademicDocument, KnowledgeChunk, SubjectSyllabus, QuestionGenerationProfile

db = SessionLocal()
try:
    docs = db.query(AcademicDocument).all()
    print(f"Auditing {len(docs)} documents...")
    total_updated = 0
    for doc in docs:
        chunks = db.query(KnowledgeChunk).filter_by(document_id=doc.id).order_by(KnowledgeChunk.chunk_index).all()
        last_module = None
        doc_updated = 0
        for chunk in chunks:
            if chunk.module_number is not None:
                last_module = chunk.module_number
            elif last_module is not None:
                chunk.module_number = last_module
                doc_updated += 1
                total_updated += 1
        print(f"  Doc '{doc.file_name}': updated {doc_updated} chunks to carry-forward module numbers")
    db.commit()
    print(f"Audit completed. Total chunks updated: {total_updated}")
finally:
    db.close()
