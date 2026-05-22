import sqlite3

conn = sqlite3.connect('qpgen.db')
cursor = conn.cursor()
cursor.execute("SELECT id, file_name, processing_status, processing_error FROM academic_documents ORDER BY id DESC LIMIT 10")
for r in cursor.fetchall():
    print(r)
