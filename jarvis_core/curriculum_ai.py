"""curriculum_ai.py — Otra IA designa tareas progresivas a Jarvis.

Inspirado en el video: 'creé otra inteligencia artificial que le designase
tareas de forma constante en cortos intervalos de tiempo y aumentando la
dificultad progresivamente'.

Niveles:
  L1 (rookie):    abrir 1 app, leer pantalla, click coordenadas simples
  L2 (intermedio): abrir 3 apps, mover/copiar/borrar archivos, navegar web
  L3 (avanzado):  multi-step coherente (abrir Excel + sumar columna + guardar)
  L4 (experto):   tareas con razonamiento (analizar gráfica y resumir)

La IA generadora es Claude CLI con un system prompt específico.
Toma como contexto el historial de aciertos/errores y propone N nuevas tareas
adecuadas al nivel actual.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from jarvis_core import queue_manager
from jarvis_trainer import memory


SYSTEM_PROMPT = """Eres el "Maestro" de Jarvis, otra IA que entrena al agente
asignandole tareas progresivas para que aprenda a usar una PC Windows como un
humano experto.

Recibes:
- Nivel actual del agente (L1/L2/L3/L4)
- Tasks completadas exitosamente (con tiempo promedio)
- Tasks que han fallado recientemente
- Numero de tasks ya en queue

Devuelves un JSON array con N nuevas tareas adecuadas al nivel + 1 reto del
siguiente nivel (challenge stretch). Formato:

[
  {"text": "abrir notepad y escribir 'hola mundo'", "level": "L2", "estimated_seconds": 8},
  {"text": "tomar screenshot del escritorio y guardarlo en Documents", "level": "L2", "estimated_seconds": 5},
  ...
]

Reglas:
1. Tareas en español natural, como las pediria un usuario humano.
2. Variar TIPOS: apps + files + browser + screen reading + multi-step.
3. NO repetir tasks que ya estan en queue (te las paso en context).
4. Subir dificultad gradualmente. Si el agente tiene >90% success rate en su
   nivel, incluir 30% de tasks del siguiente nivel.
5. Maximo 5 tasks por llamada.
6. Solo el JSON array. Sin markdown, sin explicacion.
"""


def assess_level(stats_summary: dict) -> str:
    """Determina nivel actual basado en mastered tasks + success rate global."""
    if not stats_summary:
        return "L1"
    total = len(stats_summary)
    mastered = sum(1 for v in stats_summary.values() if v.get("mastered"))
    avg_rate = sum(v.get("success_rate", 0) for v in stats_summary.values()) / max(total, 1)

    if mastered >= 30 and avg_rate >= 0.95:
        return "L4"
    if mastered >= 15 and avg_rate >= 0.90:
        return "L3"
    if mastered >= 5 and avg_rate >= 0.80:
        return "L2"
    return "L1"


def call_claude(system: str, user: str, timeout: int = 120) -> str:
    claude = shutil.which("claude") or shutil.which("claude.cmd") or "claude"
    sys_file = tempfile.NamedTemporaryFile(
        mode="w", suffix="_curriculum.md", delete=False, encoding="utf-8"
    )
    sys_file.write(system)
    sys_file.close()
    try:
        proc = subprocess.run(
            [claude, "-p", user,
             "--system-prompt-file", sys_file.name,
             "--dangerously-skip-permissions",
             "--model", "claude-sonnet-4-6"],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    finally:
        try:
            os.unlink(sys_file.name)
        except Exception:
            pass
    if proc.returncode != 0:
        raise RuntimeError(f"claude curriculum: {proc.stderr[:300]}")
    return proc.stdout


def generate_tasks(n: int = 3) -> list[dict]:
    """Llama a Claude para que designe N tareas nuevas adaptadas al nivel."""
    summary = memory.summarize_learnings()
    level = assess_level(summary)

    queue_state = queue_manager.list_tasks(status="pending")
    queue_texts = [t["text"] for t in queue_state[-10:]]

    user_prompt = json.dumps({
        "level": level,
        "tasks_in_queue": queue_texts,
        "mastered_count": sum(1 for v in summary.values() if v.get("mastered")),
        "n_tasks_requested": n,
        "stats_top5": dict(list(summary.items())[:5]),
    }, ensure_ascii=False, indent=2)

    raw = call_claude(SYSTEM_PROMPT, user_prompt)

    import re
    match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"no JSON array en respuesta: {raw[:200]}")
    tasks = json.loads(match.group(0))

    added = []
    for t in tasks[:n]:
        if t.get("text") and t["text"] not in queue_texts:
            task = queue_manager.add_task(
                text=t["text"],
                source=f"curriculum_ai_{level}",
                priority=4,
            )
            added.append({**task, "level": t.get("level", level)})
    return added


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    added = generate_tasks(n)
    print(f"Generadas {len(added)} tasks nuevas:")
    for a in added:
        print(f"  [{a.get('level','?')}] {a['text']}")
