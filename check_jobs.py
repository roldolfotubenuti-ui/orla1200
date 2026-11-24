from core.db_manager import DatabaseManager

db = DatabaseManager.get_instance()
print('DB PATH:', db.db_path)
with db.get_connection() as conn:
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print('TABLES:', tables)
    if 'jobs' in tables:
        rows = [dict(r) for r in conn.execute("SELECT id, filename, schedule_time, status, caption, file_path FROM jobs").fetchall()]
        print(f'JOBS COUNT: {len(rows)}')
        for r in rows:
            print(r)
