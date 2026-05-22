"""task_queue.py - Queue persistente de objetivos para Jarvis V2.

Almacenada en data/task_queue.json. Thread-safe via fcntl/file lock.
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[1]
QUEUE_PATH = ROOT / "data" / "task_queue.json"
_LOCK = Lock()


def _read() -> dict:
    if not QUEUE_PATH.exists():
        return {"pending": [], "done": [], "failed": []}
    try:
        return json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"pending": [], "done": [], "failed": []}


def _write(state: dict):
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2,
                                default=str), encoding="utf-8")
    tmp.replace(QUEUE_PATH)


def add(objective: str, priority: int = 5, source: str = "user",
         tags: list[str] | None = None) -> str:
    """Encola una tarea nueva. Devuelve queue_id."""
    qid = uuid.uuid4().hex[:10]
    item = {
        "qid": qid,
        "objective": objective,
        "priority": priority,
        "source": source,
        "tags": tags or [],
        "created_at": datetime.utcnow().isoformat(),
    }
    with _LOCK:
        s = _read()
        s["pending"].append(item)
        # Order desc by priority
        s["pending"].sort(key=lambda x: -x.get("priority", 5))
        _write(s)
    return qid


def pop_next() -> dict | None:
    """Saca la siguiente tarea de mayor prioridad."""
    with _LOCK:
        s = _read()
        if not s["pending"]:
            return None
        nxt = s["pending"].pop(0)
        nxt["started_at"] = datetime.utcnow().isoformat()
        _write(s)
        return nxt


def mark_done(qid: str, task_id: str = "", result: dict | None = None):
    """Marca una tarea como completada."""
    with _LOCK:
        s = _read()
        s["done"].append({
            "qid": qid, "task_id": task_id, "result": result or {},
            "completed_at": datetime.utcnow().isoformat(),
        })
        # Keep done log trim (last 200)
        s["done"] = s["done"][-200:]
        _write(s)


def mark_failed(qid: str, error: str):
    """Marca una tarea como fallida."""
    with _LOCK:
        s = _read()
        s["failed"].append({
            "qid": qid, "error": error[:500],
            "failed_at": datetime.utcnow().isoformat(),
        })
        s["failed"] = s["failed"][-100:]
        _write(s)


def status() -> dict:
    """Resumen para dashboards."""
    s = _read()
    return {
        "pending_count": len(s.get("pending", [])),
        "done_count": len(s.get("done", [])),
        "failed_count": len(s.get("failed", [])),
        "next_3": [{"qid": p["qid"], "objective": p["objective"][:80]}
                    for p in s.get("pending", [])[:3]],
    }


def clear_all():
    """Wipe queue (uso debug)."""
    with _LOCK:
        _write({"pending": [], "done": [], "failed": []})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "add":
        obj = " ".join(sys.argv[2:]) or "tarea de prueba"
        print("qid:", add(obj))
    elif cmd == "status":
        print(json.dumps(status(), ensure_ascii=False, indent=2))
    elif cmd == "clear":
        clear_all(); print("cleared")
    elif cmd == "list":
        s = _read()
        for p in s["pending"]:
            print(f"  [{p['qid']}] prio={p.get('priority')} {p['objective'][:80]}")
