import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import Base, engine, SessionLocal
# Import all models to ensure they register
from app.models import *
from app.academic.models import *

Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    docs = db.query(AcademicDocument).all()
    chunks = db.query(KnowledgeChunk).all()
    print(f"Docs total: {len(docs)}")
    print(f"Chunks total: {len(chunks)}")
    print(f"Chunks with embeddings: {sum(1 for c in chunks if c.embedding_vector is not None)}")
    print(f"Chunks with module_number: {sum(1 for c in chunks if c.module_number is not None)}")
    module_counts = {}
    for c in chunks:
        if c.module_number is not None:
            module_counts[c.module_number] = module_counts.get(c.module_number, 0) + 1
    for m in sorted(module_counts.keys()):
        print(f"  Module {m}: {module_counts[m]} chunks")
finally:
    db.close()
