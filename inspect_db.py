import sqlite3
import json

db_path = r'e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\tks_jobs.db'
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in c.fetchall()]
print("Tables:", tables)

for t in tables:
    c.execute(f"SELECT * FROM {t}")
    cols = [d[0] for d in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    print(f"\n=== {t} ({len(rows)}) ===")
    print(json.dumps(rows, indent=2, default=str))

conn.close()
