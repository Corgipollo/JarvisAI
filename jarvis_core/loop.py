"""loop.py — Loop principal de Jarvis. Vive 24/7.

Cada tick:
  1. Recolecta metricas del sistema
  2. Actualiza state machine
  3. Si IDLE y queue no vacia → toma siguiente tarea
  4. Procesa tarea (skills locales O ask_brain)
  5. Marca completada/fallida
  6. Cada N ticks idle → curriculum_ai genera nuevas tareas
  7. Loguea estado para que la UI lo muestre

Tick = 2-5 segundos. NO usa CPU intensivo en tick (psutil ya cachea).
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_core import queue_manager, curriculum_ai           # noqa: E402
from jarvis_core.state_machine import (                        # noqa: E402
    StateMachine, JarvisState, collect_metrics, AVATAR_EXPRESSION,
)


STATE_FILE = ROOT / "data" / "jarvis_live_state.json"
LOG_FILE = ROOT / "data" / "jarvis_loop.log"


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_live_state(machine: StateMachine, current_task: dict | None,
                     last_completed: dict | None) -> None:
    """Snapshot publicado para que la UI/avatar lo lea."""
    s = machine.state
    expr = AVATAR_EXPRESSION[s]
    snap = {
        "ts": time.time(),
        "state": s.value,
        "expression": expr,
        "current_task": current_task,
        "last_completed": last_completed,
        "queue_stats": queue_manager.stats(),
        "history_count": len(machine.history),
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(snap, ensure_ascii=False, indent=2),
                          encoding="utf-8")


async def execute_task(task: dict) -> dict:
    """Ejecuta una task vía nlp.execute_natural (cascade simple → ask_brain)."""
    from backend.skills.nlp import execute_natural
    log(f"[execute] {task['text'][:80]}")
    try:
        result = await execute_natural(task["text"])
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


async def run_loop(tick_seconds: int = 3,
                   curriculum_every_n_idle_ticks: int = 60,
                   max_queue_size: int = 20):
    """Loop principal. NUNCA termina."""
    machine = StateMachine()
    completed_recent = deque(maxlen=20)
    errors_recent = deque(maxlen=20)
    idle_ticks = 0

    log("=== Jarvis loop INICIADO ===")
    write_live_state(machine, None, None)

    last_completed = None

    while True:
        # 1. Métricas + estado
        stats = queue_manager.stats()
        in_progress = stats["in_progress"]
        m = collect_metrics(
            queue_size=stats["pending"],
            in_progress=in_progress,
            completed_recent=sum(1 for ts in completed_recent if time.time() - ts < 60),
            errors_recent=sum(1 for ts in errors_recent if time.time() - ts < 60),
        )
        new_state = machine.update(m)

        # 2. Si IDLE y hay pendings → tomar y procesar
        current_task = None
        if new_state == JarvisState.IDLE and stats["pending"] > 0:
            task = queue_manager.next_pending()
            if task:
                queue_manager.mark_in_progress(task["id"])
                current_task = task
                machine.update(m)  # transición a WORKING
                write_live_state(machine, current_task, last_completed)

                result = await execute_task(task)
                if result.get("success"):
                    queue_manager.mark_completed(task["id"], result)
                    completed_recent.append(time.time())
                    last_completed = {**task, "result_short": str(result)[:200]}
                    log(f"[OK] {task['id']} {task['text'][:60]}")
                else:
                    queue_manager.mark_failed(task["id"], str(result.get("error", "")))
                    errors_recent.append(time.time())
                    last_completed = {**task, "result_short": str(result)[:200]}
                    log(f"[FAIL] {task['id']} {task['text'][:60]}")
                idle_ticks = 0
        else:
            idle_ticks += 1

        # 3. Curriculum: si llevamos N ticks idle Y queue chica → pedir más tareas
        if (idle_ticks >= curriculum_every_n_idle_ticks
                and stats["pending"] < max_queue_size
                and new_state in (JarvisState.IDLE, JarvisState.SLEEPING)):
            log(f"[curriculum] idle {idle_ticks} ticks, generando nuevas tareas...")
            try:
                added = curriculum_ai.generate_tasks(n=3)
                log(f"[curriculum] +{len(added)} tareas")
                idle_ticks = 0
            except Exception as e:
                log(f"[curriculum] error: {e}")
                idle_ticks = 0  # reset para no spammear

        # 4. Snapshot para UI
        write_live_state(machine, current_task, last_completed)

        # 5. Tick
        await asyncio.sleep(tick_seconds)


if __name__ == "__main__":
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        log("Loop detenido por usuario")
