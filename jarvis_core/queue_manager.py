"""queue_manager.py — Cola persistente de tareas (como TASKS_PENDING del video).

Backend: JSON simple. Lecturas y escrituras atómicas con flock-like via temp file.
Cada tarea: {id, text, source, priority, status, created_at, started_at, completed_at, result}

Estados de tarea: pending, in_progress, completed, failed, cancelled
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
QUEUE_FILE = DATA_DIR / "jarvis_queue.json"


def _load() -> list[dict]:
    if not QUEUE_FILE.exists():
        return []
    try:
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = QUEUE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, QUEUE_FILE)


def add_task(text: str, source: str = "user", priority: int = 5) -> dict:
    items = _load()
    task = {
        "id": str(uuid.uuid4())[:8],
        "text": text,
        "source": source,
        "priority": priority,
        "status": "pending",
        "created_at": time.time(),
        "started_at": None,
        "completed_at": None,
        "result": None,
    }
    items.append(task)
    _save(items)
    return task


def list_tasks(status: str | None = None) -> list[dict]:
    items = _load()
    if status:
        items = [t for t in items if t["status"] == status]
    return items


def next_pending() -> dict | None:
    items = _load()
    pendings = [t for t in items if t["status"] == "pending"]
    if not pendings:
        return None
    pendings.sort(key=lambda t: (-t["priority"], t["created_at"]))
    return pendings[0]


def mark_in_progress(task_id: str) -> bool:
    items = _load()
    for t in items:
        if t["id"] == task_id:
            t["status"] = "in_progress"
            t["started_at"] = time.time()
            _save(items)
            return True
    return False


def mark_completed(task_id: str, result: dict | str) -> bool:
    items = _load()
    for t in items:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["completed_at"] = time.time()
            t["result"] = result
            _save(items)
            return True
    return False


def mark_failed(task_id: str, error: str) -> bool:
    items = _load()
    for t in items:
        if t["id"] == task_id:
            t["status"] = "failed"
            t["completed_at"] = time.time()
            t["result"] = {"error": error}
            _save(items)
            return True
    return False


def stats() -> dict:
    items = _load()
    counts = {"pending": 0, "in_progress": 0, "completed": 0, "failed": 0, "cancelled": 0}
    for t in items:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    return {
        "total": len(items),
        **counts,
        "next": next_pending(),
    }


def clear_completed(keep_last: int = 50) -> int:
    """Borra completed/failed antiguos, mantiene los N más recientes."""
    items = _load()
    done = [t for t in items if t["status"] in ("completed", "failed")]
    pending = [t for t in items if t["status"] not in ("completed", "failed")]
    done.sort(key=lambda t: t.get("completed_at") or 0, reverse=True)
    kept = done[:keep_last]
    new = pending + kept
    removed = len(items) - len(new)
    _save(new)
    return removed
