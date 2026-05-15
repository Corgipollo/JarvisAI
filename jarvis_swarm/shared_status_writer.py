"""shared_status_writer.py — Escribe estado de Jarvis al shared folder VM↔host.

Cada 15s copia data/unified_context.json + métricas resumidas a:
  \\VBOXSVR\jarvis_shared\status.json

Permite al host leer estado en tiempo real sin guestcontrol.
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
SHARED_TARGETS = [
    Path(r"\\VBOXSVR\jarvis_shared"),
    Path("Z:/"),
    Path("Y:/"),
    Path("X:/"),
]


def find_shared() -> Path | None:
    for p in SHARED_TARGETS:
        try:
            if p.exists():
                return p
        except OSError:
            continue
    return None


def count_files(p: Path, pat: str = "*.json") -> int:
    if not p.exists():
        return 0
    return len([f for f in p.glob(pat) if not f.name.startswith("_")])


def tail_jsonl(p: Path, n: int = 5) -> list:
    if not p.exists():
        return []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(l) for l in lines if l.strip()]
    except Exception:
        return []


def safe_load(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def build_status() -> dict:
    skills_dir = DATA / "skill_library"
    gaps = safe_load(DATA / "gaps.json")
    unified = safe_load(DATA / "unified_context.json")
    return {
        "ts": datetime.now().isoformat(),
        "skills_count": count_files(skills_dir),
        "pending_gaps": len(gaps.get("queries", [])),
        "first_5_pending": gaps.get("queries", [])[:5],
        "recent_coach": tail_jsonl(DATA / "coach_decisions.jsonl", 5),
        "recent_errors": tail_jsonl(DATA / "jarvis_errors.jsonl", 5),
        "recent_swarm_events": tail_jsonl(DATA / "swarm_memory.jsonl", 10),
        "active_task": safe_load(DATA / "active_task_state.json"),
        "screen": (unified.get("screen") or {}).get("active_window", ""),
        "host_resources": unified.get("host_resources", {}),
        "swarm_procs_count": len(unified.get("swarm_processes", [])),
    }


def main():
    target = find_shared()
    if target is None:
        print(f"[status_writer] shared folder no encontrado en {SHARED_TARGETS}, reintentando 30s...", flush=True)
        time.sleep(30)
        return main()
    print(f"[status_writer] escribiendo a {target}/status.json cada 15s", flush=True)
    while True:
        try:
            status = build_status()
            (target / "status.json").write_text(
                json.dumps(status, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8"
            )
            # Also copy unified_context for full context
            uc = DATA / "unified_context.json"
            if uc.exists():
                shutil.copy(uc, target / "unified_context.json")
        except Exception as e:
            print(f"[status_writer] error: {e}", flush=True)
        time.sleep(15)


if __name__ == "__main__":
    main()
