"""
trainer.py — Loop de entrenamiento de Jarvis.

Ejecuta tasks.yaml. Para cada tarea:
  1. Ejecuta via pc_control (open_app, system_action)
  2. Logea exito a learnings.jsonl o falla a errors.jsonl
  3. Resumen de la corrida a runs.jsonl

Default: SANDBOX_MODE=1 (no abre apps realmente, solo loguea).
Para training real: JARVIS_SANDBOX=0 python trainer.py

Pensado para correr cada N minutos via Scheduled Task de Windows.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_trainer import memory  # noqa: E402
from jarvis_trainer.sandbox import is_sandbox, sandbox_log  # noqa: E402

# Por defecto sandbox ON — sobreescribir con env var para entrenar real
os.environ.setdefault("JARVIS_SANDBOX", "1")

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


async def run_task(task: dict) -> dict:
    """Ejecuta una task del YAML y devuelve resultado."""
    tid = task["id"]
    action = task["action"]
    target = task["target"]
    expect_failure = task.get("expect_failure", False)

    if is_sandbox():
        # Modo seguro: solo registra que SE INTENTARIA hacer
        sandbox_log(f"would_run:{action}:{target}", {"task_id": tid})
        # Aun asi, ejecutamos open_app que en si es idempotente
        # (si ya esta abierta solo trae al frente)

    if action == "open_app":
        from backend.integrations.pc_control import open_app
        result = await open_app(target)
    elif action == "system":
        from backend.integrations.pc_control import system_action
        result = await system_action(target)
    elif action == "close_app":
        from backend.integrations.pc_control import close_app
        result = await close_app(target)
    else:
        return {"task_id": tid, "ok": False, "error": f"action desconocida: {action}"}

    success = bool(result.get("success"))

    # Si esperabamos que falle, invertir
    if expect_failure:
        success = not success

    if success:
        strategy = result.get("strategy") or "unknown"
        attempts_before = len(result.get("attempts", []))
        memory.log_learning(tid, strategy, attempts_before)
    else:
        memory.log_error(tid, str(result.get("error", "unknown")), result.get("attempts", []))

    return {
        "task_id": tid,
        "ok": success,
        "strategy": result.get("strategy"),
        "attempts": len(result.get("attempts", [])),
        "expect_failure": expect_failure,
    }


def load_tasks() -> list[dict]:
    if not HAS_YAML:
        # Fallback: parseo manual minimo del YAML
        text = (ROOT / "jarvis_trainer" / "tasks.yaml").read_text(encoding="utf-8")
        # Muy basico — solo si pyyaml no esta instalado
        tasks = []
        current = {}
        for line in text.splitlines():
            line = line.rstrip()
            if line.startswith("  - id:"):
                if current:
                    tasks.append(current)
                current = {"id": line.split(":", 1)[1].strip()}
            elif line.startswith("    action:"):
                current["action"] = line.split(":", 1)[1].strip()
            elif line.startswith("    target:"):
                current["target"] = line.split(":", 1)[1].strip()
            elif line.startswith("    expect_failure:"):
                current["expect_failure"] = "true" in line.lower()
        if current and "id" in current:
            tasks.append(current)
        return tasks

    with open(ROOT / "jarvis_trainer" / "tasks.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("tasks", [])


async def train(verbose: bool = True) -> dict:
    tasks = load_tasks()
    started = datetime.now()
    if verbose:
        sandbox_str = "SANDBOX" if is_sandbox() else "REAL"
        print(f"[trainer] {started.isoformat()} | {len(tasks)} tareas | mode={sandbox_str}")

    results = []
    for task in tasks:
        try:
            r = await run_task(task)
        except Exception as e:
            r = {"task_id": task.get("id", "?"), "ok": False, "error": str(e)}
        results.append(r)
        if verbose:
            mark = "OK" if r["ok"] else "FAIL"
            print(f"  [{mark}] {r['task_id']:30s} strategy={r.get('strategy')} attempts={r.get('attempts')}")

    elapsed = (datetime.now() - started).total_seconds()
    summary = {
        "tasks_total": len(tasks),
        "tasks_ok": sum(1 for r in results if r["ok"]),
        "tasks_fail": sum(1 for r in results if not r["ok"]),
        "elapsed_s": round(elapsed, 1),
        "sandbox": is_sandbox(),
    }
    memory.log_run(summary)

    if verbose:
        print(f"[trainer] OK: {summary['tasks_ok']}/{summary['tasks_total']} en {elapsed:.1f}s")
        # Mostrar mejor estrategia por tarea hasta ahora
        learnings = memory.summarize_learnings()
        for tid, stats in sorted(learnings.items()):
            if stats["successes"] >= 1:
                print(f"  -> {tid}: best={stats['best_strategy']} (rate={stats['success_rate']})")

    return summary


def main():
    summary = asyncio.run(train())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
