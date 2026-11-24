import sqlite3
import json

conn = sqlite3.connect(r'e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\tks_jobs.db')
c = conn.cursor()
c.execute("SELECT id, department_id, account_id, status, error_code, error_message, updated_at FROM jobs ORDER BY rowid DESC LIMIT 6")
cols = [d[0] for d in c.description]
rows = [dict(zip(cols, r)) for r in c.fetchall()]
print(json.dumps(rows, indent=2))
conn.close()
