import sqlite3

conn = sqlite3.connect(r'e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\tks_jobs.db')
c = conn.cursor()
c.execute("UPDATE account_assignments SET enabled=0 WHERE account_id='14cb6dda-4a0a-4bc7-86a8-05d126af8e00'")
conn.commit()
print("Disabled legacy assignment for 14cb6dda. Rows affected:", c.rowcount)
conn.close()
