import sqlite3
import json

conn = sqlite3.connect(r'e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\tks_jobs.db')
c = conn.cursor()
c.execute("SELECT id, account_id, department_id, platform, round_robin_order, enabled, created_at FROM account_assignments")
cols = [d[0] for d in c.description]
rows = [dict(zip(cols, r)) for r in c.fetchall()]
print(json.dumps(rows, indent=2))
conn.close()
