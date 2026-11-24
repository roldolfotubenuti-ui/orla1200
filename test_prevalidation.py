import sys
import json
import sqlite3
from pathlib import Path

sys.path.insert(0, r"e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine")

from core.account_manager import AccountManager

DRIVE_FOLDERS = {
    "dept_instagram": {
        "name": "Instagram",
        "employee_id": "employee-01",
        "drawer_id": "drawer-01",
        "folder_id": "1_EkgBi7YQkLha92WDJk_UJkWalPZtBhi",
        "url": "https://drive.google.com/drive/folders/1_EkgBi7YQkLha92WDJk_UJkWalPZtBhi"
    },
    "dept_mercadolivre": {
        "name": "Mercado Livre",
        "employee_id": "employee-02",
        "drawer_id": "drawer-02",
        "folder_id": "1BIT-D_0rTUKuQeEQLooNnl89gzsostjs",
        "url": "https://drive.google.com/drive/folders/1BIT-D_0rTUKuQeEQLooNnl89gzsostjs"
    },
    "dept_shorts": {
        "name": "Shorts",
        "employee_id": "employee-03",
        "drawer_id": "drawer-03",
        "folder_id": "1E8ljEe1tzaTeurNDkGXowMmEEh_21M6w",
        "url": "https://drive.google.com/drive/folders/1E8ljEe1tzaTeurNDkGXowMmEEh_21M6w"
    },
    "dept_tiktok": {
        "name": "TikTok",
        "employee_id": "employee-04",
        "drawer_id": "drawer-04",
        "folder_id": "1o0L9RN-yzxzzrVbBTY8H8dU7PcHA4Sgi",
        "url": "https://drive.google.com/drive/folders/1o0L9RN-yzxzzrVbBTY8H8dU7PcHA4Sgi"
    },
    "dept_tiktokshop": {
        "name": "TikTok Shop",
        "employee_id": "employee-05",
        "drawer_id": "drawer-05",
        "folder_id": "15DSKr0vn2fV3n-3FwI-m_4HR8XZI1hEP",
        "url": "https://drive.google.com/drive/folders/15DSKr0vn2fV3n-3FwI-m_4HR8XZI1hEP"
    },
    "dept_youtube": {
        "name": "YouTube",
        "employee_id": "employee-06",
        "drawer_id": "drawer-06",
        "folder_id": "1gjgMgqK0488Q2xm1ZOipQSC73XLI7rDr",
        "url": "https://drive.google.com/drive/folders/1gjgMgqK0488Q2xm1ZOipQSC73XLI7rDr"
    }
}

def audit_mappings():
    mgr = AccountManager()
    accounts = mgr.list_accounts()
    acc_map = {a.account_id: a for a in accounts}
    
    conn = sqlite3.connect(r'e:\youtube\APPS CURSOR\AAALEKLEK\tks-engine\storage\tks_jobs.db')
    c = conn.cursor()
    c.execute("SELECT id, name, employee_id, drawer_id FROM departments WHERE enabled=1 ORDER BY id")
    depts = c.fetchall()
    
    c.execute("SELECT department_id, account_id, platform, round_robin_order FROM account_assignments WHERE enabled=1 ORDER BY round_robin_order")
    assignments = c.fetchall()
    
    conn.close()
    
    report = []
    
    for d_id, d_name, d_emp, d_drawer in depts:
        drive_info = DRIVE_FOLDERS.get(d_id, {})
        # Find assignment
        assigned = [a for a in assignments if a[0] == d_id]
        
        acc_info = None
        if assigned:
            acc_id = assigned[0][1]
            acc = acc_map.get(acc_id)
            if acc:
                acc_info = {
                    "account_id": acc.account_id,
                    "title": acc.display_title or acc.username,
                    "platform": acc.platform,
                    "detected_user": acc.username,
                    "status": acc.auth_status,
                    "cookie_count": acc.cookie_count
                }
        
        report.append({
            "department_id": d_id,
            "department_name": d_name,
            "employee_id": drive_info.get("employee_id", f"employee-{d_emp}"),
            "drawer_id": drive_info.get("drawer_id", d_drawer),
            "folder_id": drive_info.get("folder_id"),
            "folder_url": drive_info.get("url"),
            "account": acc_info
        })
        
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    audit_mappings()
