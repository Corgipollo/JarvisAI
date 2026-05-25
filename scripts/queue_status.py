"""queue_status.py - Snapshot rapido del estado de la queue Jarvis."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "data" / "tenants" / "default" / "memory.db"
if not DB.exists():
    print(f"DB no existe: {DB}")
    raise SystemExit(1)

con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
cur = con.cursor()

try:
    cur.execute("SELECT status, COUNT(*) as n FROM task_queue GROUP BY status")
    print("=== Queue por estado ===")
    for r in cur.fetchall():
        print(f"  {r['status']}: {r['n']}")

    cur.execute(
        "SELECT id, status, priority, substr(objective, 1, 100) as obj, "
        "created_at FROM task_queue ORDER BY id DESC LIMIT 8"
    )
    print("\n=== Ultimas 8 tareas ===")
    for r in cur.fetchall():
        print(f"  #{r['id']} [{r['status']}] p{r['priority']}: {r['obj']}")

    cur.execute(
        "SELECT id, status, substr(objective, 1, 80) as obj, started_at, "
        "completed_at, result FROM task_queue WHERE status IN ('running','completed') "
        "ORDER BY id DESC LIMIT 3"
    )
    print("\n=== Tareas con resultado (ultimas 3) ===")
    for r in cur.fetchall():
        res = (r["result"] or "")[:200] if r["result"] else "(sin resultado)"
        print(f"  #{r['id']} [{r['status']}] {r['obj']}")
        print(f"    started: {r['started_at']}  completed: {r['completed_at']}")
        print(f"    result: {res}")
finally:
    con.close()
