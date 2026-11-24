import sqlite3

conn = sqlite3.connect('storage/tks_jobs.db')
conn.row_factory = sqlite3.Row
# Remover jobs duplicados de 2026-11-24 para manter rigorosamente 1 job por conta/pasta para hoje
conn.execute("DELETE FROM jobs WHERE schedule_time LIKE '2026-11-24%'")
conn.commit()

rows = conn.execute("SELECT id, filename, schedule_time, status, caption, file_path FROM jobs WHERE status = 'READY_FOR_UPLOAD'").fetchall()
print(f'ACTIVE READY JOBS ({len(rows)}):')
for r in rows:
    print(dict(r))
