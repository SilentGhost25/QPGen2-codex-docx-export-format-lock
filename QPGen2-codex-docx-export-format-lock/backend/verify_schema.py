import sqlite3

conn = sqlite3.connect('qpgen.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(paper_questions)")
columns = cursor.fetchall()
print('paper_questions columns:')
for col in columns:
    print(f'  {col[1]} - {col[2]}')
conn.close()
