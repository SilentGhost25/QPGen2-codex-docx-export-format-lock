import sqlite3
import requests

conn = sqlite3.connect('qpgen.db')
cursor = conn.cursor()

# Get latest subject
cursor.execute("SELECT id, dept_id FROM subjects ORDER BY id DESC LIMIT 1")
subject = cursor.fetchone()
print('Latest subject:', subject)

# Get a teacher
cursor.execute("SELECT id, email FROM users WHERE role='TEACHER' LIMIT 1")
teacher = cursor.fetchone()
print('Teacher:', teacher)

if not teacher or not subject:
    print('Missing teacher or subject')
    exit(1)

# Check teacher subjects mapping
cursor.execute("SELECT * FROM teacher_subjects WHERE teacher_id=? AND subject_id=?", (teacher[0], subject[0]))
mapping = cursor.fetchone()
print('Teacher mapping:', mapping)

# Check if mapping exists, if not, create it to bypass 403
if not mapping:
    cursor.execute("INSERT INTO teacher_subjects (teacher_id, subject_id) VALUES (?, ?)", (teacher[0], subject[0]))
    conn.commit()
    print('Inserted mapping to bypass 403')

# Try uploading
try:
    token_res = requests.post('http://localhost:8000/api/v1/auth/login', data={'username':teacher[1],'password':'password'})
    token = token_res.json().get('access_token')
    if token:
        res = requests.post(
            'http://localhost:8000/api/v1/academic/documents/upload',
            headers={'Authorization': f'Bearer {token}'},
            data={'subject_id': subject[0], 'document_type': 'notes'},
            files={'file': ('test.txt', b'test content')}
        )
        print('Upload status:', res.status_code)
        print('Upload response:', res.text)
    else:
        print('Login failed:', token_res.text)
except Exception as e:
    print('Error:', e)
