"""state_backup.py — Auto-commit + push del estado a GitHub cada N learnings.

Watch data/skill_library/_index.jsonl. Cuando llega a N skills nuevas (default 5),
ejecuta git add + commit + push al repo. Si la VM crashea, recovery vía git pull.

Uso:
    python jarvis_bridge/state_backup.py        # loop infinito, watch
    python jarvis_bridge/state_backup.py once   # commit + push uno solo
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "skill_library" / "_index.jsonl"
STATE_FILE = ROOT / "data" / ".backup_state.json"
COMMIT_EVERY_N = 5
CHECK_EVERY_S = 60


def count_skills() -> int:
    if not INDEX.exists():
        return 0
    return sum(1 for line in INDEX.read_text(encoding="utf-8").splitlines() if line.strip())


def last_backup_count() -> int:
    if not STATE_FILE.exists():
        return 0
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("last_count", 0)
    except Exception:
        return 0


def write_state(count: int):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"last_count": count, "ts": time.time()}, indent=2), encoding="utf-8")


def run(cmd: list[str], cwd: Path = ROOT) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)
    return proc.returncode, (proc.stdout + proc.stderr)[:500]


def commit_and_push() -> bool:
    current = count_skills()
    msg = f"jarvis state backup: {current} skills + roles + learnings ({time.strftime('%Y-%m-%d %H:%M')})"

    print(f"[state_backup] commiting {current} skills...", flush=True)
    run(["git", "add", "data/skill_library/", "data/role_library/",
         "data/jarvis_learnings.jsonl", "data/jarvis_runs.jsonl",
         "data/gaps_addressed.jsonl", "data/gaps.json"])
    rc, out = run(["git", "commit", "-m", msg])
    if "nothing to commit" in out:
        print("  nothing to commit, skipping push")
        return False
    if rc != 0:
        print(f"  commit fallo: {out[:200]}")
        return False
    rc, out = run(["git", "push", "origin", "master"])
    if rc != 0:
        print(f"  push fallo: {out[:200]}")
        return False
    write_state(current)
    print(f"  OK pushed {current} skills")
    return True


def watch_loop():
    print(f"[state_backup] watch loop activo. commit cada {COMMIT_EVERY_N} skills nuevas.")
    while True:
        try:
            current = count_skills()
            last = last_backup_count()
            if current - last >= COMMIT_EVERY_N:
                commit_and_push()
            time.sleep(CHECK_EVERY_S)
        except KeyboardInterrupt:
            print("[state_backup] detenido")
            break
        except Exception as e:
            print(f"[state_backup] error: {e}")
            time.sleep(30)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        commit_and_push()
    else:
        watch_loop()
