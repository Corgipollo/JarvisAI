"""jarvis_api.py - FastAPI server que vive en la VM y recibe ordenes del host.

Arquitectura cliente-servidor:
  - HOST: voice_daemon captura voz, transcribe, POST a este endpoint
  - VM: este server recibe, dispatcha a SwarmOrchestrator / graph.run_objective

Endpoints:
  GET  /health          - heartbeat check
  GET  /status          - lee data/status_board.json
  POST /execute         - {objective: str, priority?: int} -> task_id
  GET  /tasks/{id}      - estado de una task lanzada
  POST /interrupt       - cancela task actual

Seguridad: auth via shared secret en header X-Jarvis-Token (env JARVIS_API_TOKEN).
Si token vacio -> bind a 127.0.0.1 only.

Run desde VM:
  python -m jarvis_v2.api.jarvis_api
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, Field
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATUS_BOARD = ROOT / "data" / "status_board.json"
TASKS_DIR = ROOT / "data" / "api_tasks"
TASKS_DIR.mkdir(parents=True, exist_ok=True)

API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "")
PORT = int(os.environ.get("JARVIS_API_PORT", "5000"))
# Si no hay token -> solo 127.0.0.1; con token -> 0.0.0.0 (accesible LAN)
HOST = os.environ.get("JARVIS_API_HOST", "0.0.0.0" if API_TOKEN else "127.0.0.1")

app = FastAPI(title="Jarvis v2 API", version="1.0")

# Mount admin routes (multi-tenant dashboard) + static HTML
try:
    from jarvis_v2.api.admin_routes import router as admin_router, serve_admin
    app.include_router(admin_router)

    @app.get("/admin")
    def _admin_html():
        return serve_admin()
except Exception as e:
    print(f"[api] admin_routes not loaded: {e}", flush=True)

# Mount stripe billing routes (subscription + webhook)
try:
    from jarvis_v2.api.stripe_billing import router as billing_router
    app.include_router(billing_router)
except Exception as e:
    print(f"[api] stripe_billing not loaded: {e}", flush=True)

# Mount signup routes (landing + wizard publicos)
try:
    from jarvis_v2.api.signup_routes import router as signup_router
    app.include_router(signup_router)
except Exception as e:
    print(f"[api] signup_routes not loaded: {e}", flush=True)

# Mount outreach routes (CRM + cold email + tracking)
try:
    from jarvis_v2.api.outreach_routes import router as outreach_router
    app.include_router(outreach_router)
except Exception as e:
    print(f"[api] outreach_routes not loaded: {e}", flush=True)

# Estado in-memory de tasks lanzadas (persiste a disco en TASKS_DIR)
_TASKS: dict = {}
_TASKS_LOCK = threading.Lock()


class ExecuteRequest(BaseModel):
    objective: str = Field(min_length=3, max_length=2000)
    priority: int = Field(default=5, ge=1, le=10)
    thread_id: str | None = None


class TaskInfo(BaseModel):
    task_id: str
    status: str
    objective: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    result: dict | None = None
    error: str | None = None


def _auth(token_header: str | None):
    """Valida token. Si API_TOKEN vacio (modo dev local), bypass."""
    if not API_TOKEN:
        return
    if token_header != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_token")


def _save_task(task: dict):
    """Persiste task a disco para query post-restart."""
    p = TASKS_DIR / f"{task['task_id']}.json"
    p.write_text(json.dumps(task, ensure_ascii=False, indent=2, default=str),
                 encoding="utf-8")


def _run_task(task_id: str, objective: str, thread_id: str | None):
    """Supervisor que lanza la task en SUBPROCESS independiente.

    Refactor 2026-05-25: antes corria en threading.Thread. Cuando LangGraph se
    colgaba cargando Florence-2/chroma, el thread no se podia matar (Python no
    soporta thread.kill) -> RAM API crecia a 11.8 GB.

    Solucion: subprocess.Popen lanza task_executor.py en proceso propio. Si se
    cuelga, process.kill() lo MATA forzosamente y libera toda su RAM al SO.
    El API queda 100% libre para responder polls del worker.
    """
    import subprocess
    with _TASKS_LOCK:
        t = _TASKS[task_id]
        t["status"] = "running"
        t["started_at"] = datetime.utcnow().isoformat()
        _save_task(t)

    timeout_sec = int(os.environ.get("JARVIS_TASK_HARD_TIMEOUT_SEC", "120"))
    py = os.environ.get("JARVIS_PYTHON", sys.executable)
    proj_root = Path(__file__).resolve().parents[2]

    cmd = [
        py, "-m", "jarvis_v2.task_executor",
        "--task-id", task_id,
        "--objective", objective,
    ]
    if thread_id:
        cmd.extend(["--thread-id", thread_id])

    proc = None
    timed_out = False
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(proj_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout_sec)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except Exception:
                stdout, stderr = "", "killed_after_timeout"
            rc = -9

        # El task_executor.py ya escribio el JSON con el resultado. Solo
        # actualizamos in-memory + agregamos info si fue killed.
        if timed_out:
            with _TASKS_LOCK:
                t = _TASKS.get(task_id, {"task_id": task_id})
                t["status"] = "error"
                t["error"] = (f"hard_timeout_killed: subprocess excedio "
                              f"{timeout_sec}s y fue terminado. "
                              f"stderr_tail: {(stderr or '')[-300:]}")
                t["completed_at"] = datetime.utcnow().isoformat()
                _save_task(t)
        else:
            # Re-cargar desde disco lo que escribio el subprocess
            p = TASKS_DIR / f"{task_id}.json"
            if p.exists():
                try:
                    fresh = json.loads(p.read_text(encoding="utf-8"))
                    with _TASKS_LOCK:
                        _TASKS[task_id] = fresh
                except Exception:
                    pass
            else:
                # Subprocess murio sin escribir -> marcar error
                with _TASKS_LOCK:
                    t = _TASKS.get(task_id, {"task_id": task_id})
                    t["status"] = "error"
                    t["error"] = f"subprocess_no_output rc={rc} stderr={(stderr or '')[-300:]}"
                    t["completed_at"] = datetime.utcnow().isoformat()
                    _save_task(t)
    except Exception as e:
        if proc:
            try:
                proc.kill()
            except Exception:
                pass
        with _TASKS_LOCK:
            t = _TASKS.get(task_id, {"task_id": task_id})
            t["status"] = "error"
            t["error"] = f"supervisor_error: {type(e).__name__}: {e}"
            t["completed_at"] = datetime.utcnow().isoformat()
            _save_task(t)


@app.get("/health")
def health():
    return {
        "ok": True,
        "ts": datetime.utcnow().isoformat(),
        "active_tasks": sum(1 for t in _TASKS.values()
                            if t.get("status") in ("running", "queued")),
        "total_tasks_lifetime": len(_TASKS),
        "api_version": "1.0",
    }


@app.get("/status")
def status(x_jarvis_token: str | None = Header(default=None)):
    """Devuelve status_board.json + algunas metricas en vivo."""
    _auth(x_jarvis_token)
    data = {}
    if STATUS_BOARD.exists():
        try:
            data = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Anadir survival signals si disponibles
    try:
        from jarvis_v2.cfo.algorithmic_death import survival_signals
        data["survival"] = survival_signals()
    except Exception as e:
        data["survival_error"] = str(e)
    return data


@app.post("/execute")
def execute(req: ExecuteRequest,
            x_jarvis_token: str | None = Header(default=None)):
    """Lanza objetivo en background. Retorna task_id."""
    _auth(x_jarvis_token)
    task_id = uuid.uuid4().hex[:12]
    task = {
        "task_id": task_id,
        "status": "queued",
        "objective": req.objective,
        "priority": req.priority,
        "created_at": datetime.utcnow().isoformat(),
    }
    with _TASKS_LOCK:
        _TASKS[task_id] = task
        _save_task(task)
    threading.Thread(
        target=_run_task, args=(task_id, req.objective, req.thread_id),
        daemon=True, name=f"task_{task_id}",
    ).start()
    return {"task_id": task_id, "status": "queued",
            "objective": req.objective[:100]}


@app.get("/tasks/{task_id}")
def get_task(task_id: str,
              x_jarvis_token: str | None = Header(default=None)) -> TaskInfo:
    _auth(x_jarvis_token)
    with _TASKS_LOCK:
        t = _TASKS.get(task_id)
    if not t:
        # Try load from disk
        p = TASKS_DIR / f"{task_id}.json"
        if p.exists():
            t = json.loads(p.read_text(encoding="utf-8"))
        else:
            raise HTTPException(status_code=404, detail="task_not_found")
    return TaskInfo(**{
        "task_id": t["task_id"], "status": t["status"],
        "objective": t["objective"], "created_at": t["created_at"],
        "started_at": t.get("started_at"),
        "completed_at": t.get("completed_at"),
        "result": t.get("result"), "error": t.get("error"),
    })


@app.get("/tasks")
def list_tasks(limit: int = 20,
                x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    with _TASKS_LOCK:
        items = sorted(_TASKS.values(),
                       key=lambda t: t.get("created_at", ""),
                       reverse=True)[:limit]
    return {"tasks": items, "total": len(_TASKS)}


@app.post("/queue/add")
def queue_add(req: ExecuteRequest,
              x_jarvis_token: str | None = Header(default=None)):
    """Encola una tarea para que el task_worker la procese asincrono."""
    _auth(x_jarvis_token)
    from jarvis_v2 import task_queue as Q
    qid = Q.add(req.objective, priority=req.priority, source="api")
    return {"qid": qid, "queued": True,
            "objective_preview": req.objective[:120]}


@app.get("/queue/status")
def queue_status(x_jarvis_token: str | None = Header(default=None)):
    """Resumen de la queue (pending/done/failed counts + next_3)."""
    _auth(x_jarvis_token)
    from jarvis_v2 import task_queue as Q
    return Q.status()


@app.post("/interrupt")
def interrupt(x_jarvis_token: str | None = Header(default=None)):
    """Cancela la task running mas reciente (best-effort)."""
    _auth(x_jarvis_token)
    # Best-effort: thread daemon no se mata limpio. Marcamos status como
    # interrupted; el ejecutor deberia checar un flag (futuro).
    cancelled = 0
    with _TASKS_LOCK:
        for t in _TASKS.values():
            if t.get("status") == "running":
                t["status"] = "interrupt_requested"
                t["interrupt_at"] = datetime.utcnow().isoformat()
                cancelled += 1
                _save_task(t)
    return {"cancelled_count": cancelled}


def main():
    print(f"=== Jarvis API v1.0 ===", flush=True)
    print(f"  host: {HOST}:{PORT}", flush=True)
    print(f"  auth: {'TOKEN_REQUIRED' if API_TOKEN else 'OPEN (localhost only)'}",
          flush=True)
    print(f"  endpoints: /health /status /execute /tasks/{{id}} /interrupt",
          flush=True)
    uvicorn.run(app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
