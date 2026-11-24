import sqlite3

conn = sqlite3.connect('storage/tks_jobs.db')
c = conn.cursor()

# Atualizar todos os jobs das 6 pastas locais para READY_FOR_UPLOAD com agendamento para 2026-11-24 18:00:00
# e legenda 'ABSURDO'
c.execute("""
UPDATE jobs 
SET status = 'READY_FOR_UPLOAD', 
    attempt_count = 0, 
    error_message = NULL, 
    schedule_time = '2026-11-24 18:00:00', 
    updated_at = datetime('now') 
WHERE file_path LIKE 'E:\\ORLA1200\\%'
""")
conn.commit()
print("Linhas atualizadas:", c.rowcount)

# Listar os 6 jobs ativos
rows = c.execute("""
SELECT id, department_id, account_id, filename, file_path, status, schedule_time 
FROM jobs 
WHERE file_path LIKE 'E:\\ORLA1200\\%' AND status = 'READY_FOR_UPLOAD'
""").fetchall()

for r in rows:
    print(r)
conn.close()
