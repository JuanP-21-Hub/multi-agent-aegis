import os
from app.main import get_db, password_hasher

if os.environ['DB_NAME'] != 'banklab_test':
    raise RuntimeError('Test DB only')
with get_db() as conn, conn.cursor() as cur:
    cur.execute('''INSERT INTO staff_users (employee_id, display_name, password_hash)
                   VALUES (%s, '브라우저검증직원', %s)''',
                (os.environ['SMOKE_STAFF_ID'], password_hasher.hash(os.environ['SMOKE_STAFF_PASSWORD'])))
