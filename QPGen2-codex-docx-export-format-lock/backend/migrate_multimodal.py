"""
Migration: Add multimodal structured content columns to academic_documents.

Run once: python migrate_multimodal.py

Safe to run multiple times (checks for column existence first).
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "qpgen.db"


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def run_migration():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    migrations = [
        # Full structured JSON: {pages: [...], summary: {...}}
        ("structured_content", "TEXT DEFAULT NULL"),
        # Fast-filter boolean flags
        ("has_equations",  "BOOLEAN NOT NULL DEFAULT 0"),
        ("has_figures",    "BOOLEAN NOT NULL DEFAULT 0"),
        ("has_tables",     "BOOLEAN NOT NULL DEFAULT 0"),
        # Counts for display
        ("equation_count", "INTEGER NOT NULL DEFAULT 0"),
        ("figure_count",   "INTEGER NOT NULL DEFAULT 0"),
        ("table_count",    "INTEGER NOT NULL DEFAULT 0"),
    ]

    # Also handle the new PARSING status — SQLite stores strings so no enum migration needed.
    # The ProcessingStatus.PARSING = "parsing" string is already safe to store.

    added = 0
    for col_name, col_def in migrations:
        if column_exists(cur, "academic_documents", col_name):
            print(f"  ✓ {col_name} already exists, skipping")
        else:
            cur.execute(f"ALTER TABLE academic_documents ADD COLUMN {col_name} {col_def}")
            print(f"  + Added column: {col_name} {col_def}")
            added += 1

    conn.commit()
    conn.close()

    print(f"\nMigration complete — {added} column(s) added to academic_documents.")


if __name__ == "__main__":
    run_migration()
