"""
memory.py — Memoria persistente de Jarvis: errores y aprendizajes.

Append-only JSONL para que se pueda leer/diff/grep facil. Una linea = un evento.

Archivos:
- data/jarvis_errors.jsonl     # cada fallo: tarea, error, estrategias probadas
- data/jarvis_learnings.jsonl  # cada exito: que estrategia funciono para que tarea
- data/jarvis_runs.jsonl       # resumen de cada training run

API:
    log_error(task, error, attempts) → guarda fallo
    log_learning(task, strategy, attempts_before) → guarda exito
    summarize_learnings() → dict {task → mejor_estrategia, win_rate}
    recommend_strategy(task) → str | None (la mejor estrategia para esa tarea)
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ERRORS_LOG = DATA_DIR / "jarvis_errors.jsonl"
LEARNINGS_LOG = DATA_DIR / "jarvis_learnings.jsonl"
RUNS_LOG = DATA_DIR / "jarvis_runs.jsonl"


def _append(file: Path, entry: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_error(task: str, error: str, attempts: list[dict]) -> None:
    _append(ERRORS_LOG, {
        "ts": datetime.now().isoformat(),
        "task": task,
        "error": error,
        "attempts": attempts,
    })


def log_learning(task: str, strategy: str, attempts_before: int) -> None:
    _append(LEARNINGS_LOG, {
        "ts": datetime.now().isoformat(),
        "task": task,
        "strategy": strategy,
        "attempts_before_success": attempts_before,
    })


def log_run(summary: dict) -> None:
    _append(RUNS_LOG, {"ts": datetime.now().isoformat(), **summary})


def _read_jsonl(file: Path) -> list[dict]:
    if not file.exists():
        return []
    rows = []
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarize_learnings() -> dict[str, dict]:
    """Devuelve {task: {best_strategy, total_attempts, success_rate}}."""
    learnings = _read_jsonl(LEARNINGS_LOG)
    errors = _read_jsonl(ERRORS_LOG)

    by_task: dict[str, dict] = defaultdict(lambda: {
        "successes": 0, "failures": 0, "strategies": Counter(),
    })
    for r in learnings:
        t = r["task"]
        by_task[t]["successes"] += 1
        by_task[t]["strategies"][r["strategy"]] += 1
    for r in errors:
        by_task[r["task"]]["failures"] += 1

    summary = {}
    for task, stats in by_task.items():
        total = stats["successes"] + stats["failures"]
        best = stats["strategies"].most_common(1)
        summary[task] = {
            "successes": stats["successes"],
            "failures": stats["failures"],
            "success_rate": round(stats["successes"] / total, 3) if total else 0,
            "best_strategy": best[0][0] if best else None,
            "best_strategy_count": best[0][1] if best else 0,
        }
    return summary


def recommend_strategy(task: str) -> str | None:
    s = summarize_learnings().get(task, {})
    return s.get("best_strategy")


if __name__ == "__main__":
    summary = summarize_learnings()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
