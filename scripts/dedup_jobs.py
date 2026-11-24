import sqlite3

conn = sqlite3.connect('storage/tks_jobs.db')
c = conn.cursor()

# Primeiro marca todos como SUPERSEDED
c.execute("UPDATE jobs SET status = 'SUPERSEDED'")

# Pastas 1..6
dept_map = {
    1: ("dept_instagram", "10d617eb-e1a7-4ed7-b8b3-acda804f3f98", "rmn.ftbl1_009_7689492826450660630.mp4"),
    2: ("dept_mercadolivre", "37bc39cd-077f-4920-95d1-b11746f0399f", "rmn.ftbl1_012_7689210188892654851.mp4"),
    3: ("dept_shorts", "669df47e-4abf-4efd-a870-934295fa7a58", "rmn.ftbl1_013_7699867073010502934.mp4"),
    4: ("dept_tiktok", "a874cfb3-700c-4b6f-aa3c-ba1e2856894e", "rmn.ftbl1_011_7686592084618349846.mp4"),
    5: ("dept_tiktokshop", "e7e6bd57-59de-4272-82b8-f20ce2487e83", "rmn.ftbl1_014_7674994821555031318.mp4"),
    6: ("dept_youtube", "4baf0564-985f-4273-b559-9787cdd86c0d", "rmn.ftbl1_027_7691404197928979734.mp4"),
}

for folder_idx, (dept_id, acc_id, fname) in dept_map.items():
    fpath = f"E:\\ORLA1200\\{folder_idx}\\{fname}"
    # Pegar o último job desse departamento
    row = c.execute(
        "SELECT id FROM jobs WHERE department_id = ? AND file_path LIKE ? ORDER BY created_at DESC LIMIT 1",
        (dept_id, f"%{folder_idx}%")
    ).fetchone()
    if row:
        job_id = row[0]
        c.execute("""
            UPDATE jobs 
            SET status = 'READY_FOR_UPLOAD',
                account_id = ?,
                filename = ?,
                file_path = ?,
                schedule_time = '2026-11-24 18:00:00',
                caption = 'ABSURDO',
                attempt_count = 0,
                error_code = NULL,
                error_message = NULL,
                updated_at = datetime('now')
            WHERE id = ?
        """, (acc_id, fname, fpath, job_id))
        print(f"Dept {dept_id}: Reativado Job {job_id} para {fpath}")

conn.commit()

# Conferir os 6 jobs exatamente
rows = c.execute("SELECT id, department_id, account_id, filename, file_path, status, schedule_time FROM jobs WHERE status = 'READY_FOR_UPLOAD'").fetchall()
print(f"Total de jobs READY_FOR_UPLOAD: {len(rows)}")
for r in rows:
    print(r)

conn.close()
