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


def log_error(task: str, error: str, attempts: list[dict], elapsed_ms: int = 0) -> None:
    _append(ERRORS_LOG, {
        "ts": datetime.now().isoformat(),
        "task": task,
        "error": error,
        "attempts": attempts,
        "elapsed_ms": elapsed_ms,
    })


def log_learning(task: str, strategy: str, attempts_before: int, elapsed_ms: int = 0) -> None:
    _append(LEARNINGS_LOG, {
        "ts": datetime.now().isoformat(),
        "task": task,
        "strategy": strategy,
        "attempts_before_success": attempts_before,
        "elapsed_ms": elapsed_ms,
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
    """Devuelve {task: {best_strategy, success_rate, avg_elapsed_ms, ...}}.

    Mide tambien velocidad: avg_elapsed_ms por task y por estrategia.
    """
    learnings = _read_jsonl(LEARNINGS_LOG)
    errors = _read_jsonl(ERRORS_LOG)

    by_task: dict[str, dict] = defaultdict(lambda: {
        "successes": 0, "failures": 0, "strategies": Counter(),
        "elapsed_total_ms": 0, "elapsed_count": 0,
        "elapsed_by_strategy": defaultdict(lambda: {"sum": 0, "n": 0}),
    })
    for r in learnings:
        t = r["task"]
        s = r.get("strategy", "unknown")
        elapsed = r.get("elapsed_ms", 0)
        by_task[t]["successes"] += 1
        by_task[t]["strategies"][s] += 1
        by_task[t]["elapsed_total_ms"] += elapsed
        by_task[t]["elapsed_count"] += 1
        by_task[t]["elapsed_by_strategy"][s]["sum"] += elapsed
        by_task[t]["elapsed_by_strategy"][s]["n"] += 1
    for r in errors:
        by_task[r["task"]]["failures"] += 1

    summary = {}
    for task, stats in by_task.items():
        total = stats["successes"] + stats["failures"]
        best = stats["strategies"].most_common(1)
        avg_ms = (stats["elapsed_total_ms"] / stats["elapsed_count"]) if stats["elapsed_count"] else 0
        per_strat = {
            s: round(d["sum"] / d["n"], 0) if d["n"] else 0
            for s, d in stats["elapsed_by_strategy"].items()
        }
        # Mejor estrategia por VELOCIDAD (no solo por frecuencia)
        strategies_with_runs = [
            (s, per_strat[s], stats["strategies"][s])
            for s in stats["strategies"]
            if stats["elapsed_by_strategy"][s]["n"] >= 3  # minimo 3 runs
        ]
        if strategies_with_runs:
            fastest = min(strategies_with_runs, key=lambda x: x[1])
            best_by_speed = fastest[0]
        else:
            best_by_speed = None
        summary[task] = {
            "successes": stats["successes"],
            "failures": stats["failures"],
            "success_rate": round(stats["successes"] / total, 3) if total else 0,
            "best_strategy": best[0][0] if best else None,
            "best_strategy_count": best[0][1] if best else 0,
            "avg_elapsed_ms": round(avg_ms, 0),
            "elapsed_by_strategy_ms": per_strat,
            "fastest_strategy": best_by_speed,
            "mastered": stats["successes"] >= 10 and stats["failures"] == 0,
        }
    return summary


def recommend_strategy_fast(task: str) -> str | None:
    """Devuelve la estrategia HISTORICAMENTE MAS RAPIDA para esta task.

    Solo cuenta estrategias con >=3 runs para no recomendar al azar.
    """
    s = summarize_learnings().get(task, {})
    return s.get("fastest_strategy")


def recommend_strategy(task: str) -> str | None:
    """Devuelve la estrategia MAS GANADORA por frecuencia."""
    s = summarize_learnings().get(task, {})
    return s.get("best_strategy")


def is_mastered(task: str) -> bool:
    """True si Jarvis domina esta tarea (>=10 exitos sin fallos)."""
    s = summarize_learnings().get(task, {})
    return s.get("mastered", False)


if __name__ == "__main__":
    summary = summarize_learnings()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
