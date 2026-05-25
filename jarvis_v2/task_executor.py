"""task_executor.py - Ejecutor INDEPENDIENTE de UNA task en su propio proceso.

REFACTOR ARQUITECTURAL 2026-05-25:
Antes _run_task corria en threading.Thread dentro de jarvis_api.py. Cuando
LangGraph se colgaba cargando Florence-2 + chromadb, el thread NO se podia
matar (Python no soporta thread.kill()) -> la RAM del API crecia hasta
agotar (4.8 GB -> 11.8 GB observado). MemoryError + API caida.

Solucion: cada task corre en SU PROPIO PROCESO Python via subprocess.Popen.
- Si se cuelga >TIMEOUT: jarvis_api hace subprocess.kill() -> instant kill,
  RAM devuelta al SO.
- El API queda libre para responder polls del worker (no se atora).
- Cada task tiene su propio espacio de memoria: leaks NO acumulan entre tasks.

CONTRATO:
    python -m jarvis_v2.task_executor --task-id TID --objective "..." [--thread-id ...]

El executor:
    1. Marca task como running en disco (data/api_tasks/{tid}.json)
    2. Importa y ejecuta run_objective(objective)
    3. Guarda resultado/error en el mismo JSON
    4. exit(0) si done, exit(1) si error

El API (jarvis_api._run_task) solo lanza este subprocess y supervisa.
NO bloquea el event loop. NO acumula memoria.
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TASKS_DIR = ROOT / "data" / "api_tasks"


def _load_task(task_id: str) -> dict:
    p = TASKS_DIR / f"{task_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"task_id": task_id, "status": "queued"}


def _save_task(task: dict) -> None:
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    p = TASKS_DIR / f"{task['task_id']}.json"
    p.write_text(json.dumps(task, indent=2, default=str), encoding="utf-8")


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%H:%M:%S")
    print(f"[executor {ts}] {msg}", flush=True)


def execute(task_id: str, objective: str, thread_id: str | None = None) -> int:
    """Ejecuta UNA task. Retorna exit code (0=done, 1=error)."""
    _log(f"start task_id={task_id} objective={objective[:80]!r}")

    # Mark running
    t = _load_task(task_id)
    t.update({
        "task_id": task_id,
        "objective": objective,
        "status": "running",
        "started_at": datetime.utcnow().isoformat(),
        "executor_pid": __import__("os").getpid(),
    })
    _save_task(t)

    exit_code = 1
    try:
        from jarvis_v2.core.graph import run_objective
        _log("graph imported, running objective...")
        result = run_objective(objective, thread_id=thread_id or f"api_{task_id}")
        rd = result or {}
        plan = rd.get("plan") or []
        last_err = rd.get("last_error")

        if not plan or last_err:
            t["status"] = "error"
            t["error"] = (last_err or "empty_plan_or_no_steps")
            exit_code = 1
        else:
            t["status"] = "done"
            exit_code = 0

        t["completed_at"] = datetime.utcnow().isoformat()
        t["result"] = {
            "plan_len": len(plan),
            "current_step": rd.get("current_step", 0),
            "done": rd.get("done", False),
            "last_error": last_err,
            "messages_tail": str(rd.get("messages", []))[-400:],
        }
        _save_task(t)
        _log(f"finished status={t['status']} plan_len={len(plan)}")

        # Registrar fallo/exito en memoria persistente
        try:
            from jarvis_v2.memory import task_failure_memory as _tfm
            if t["status"] == "done":
                _tfm.record_success(objective)
            else:
                _tfm.record_failure(
                    objective=objective,
                    error_msg=str(t.get("error", "")),
                    hint="ejecutado en subprocess; ver task_id en api_tasks/",
                )
        except Exception:
            pass

    except Exception as e:
        tb = traceback.format_exc()
        _log(f"EXCEPTION: {e}\n{tb}")
        t["status"] = "error"
        t["completed_at"] = datetime.utcnow().isoformat()
        t["error"] = f"{type(e).__name__}: {e}"
        t["traceback_tail"] = tb[-1000:]
        _save_task(t)
        exit_code = 1
    finally:
        # Cleanup nuclear: aunque el proceso muere igual (lo cual libera TODO),
        # esto ayuda si el subprocess no termina inmediatamente.
        try:
            gc.collect()
        except Exception:
            pass
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    return exit_code


def main():
    p = argparse.ArgumentParser(description="Ejecuta 1 task Jarvis en proceso independiente.")
    p.add_argument("--task-id", required=True)
    p.add_argument("--objective", required=True)
    p.add_argument("--thread-id", default=None)
    args = p.parse_args()
    rc = execute(args.task_id, args.objective, args.thread_id)
    sys.exit(rc)


if __name__ == "__main__":
    main()
