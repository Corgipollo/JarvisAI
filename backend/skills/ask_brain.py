"""ask_brain.py — Cuando Jarvis no sabe que hacer, le pregunta a Claude.

Claude responde con un PLAN JSON de acciones a ejecutar:
[
  {"action": "press_keys", "args": ["win"]},
  {"action": "type_text", "args": ["telegram"]},
  {"action": "press_keys", "args": ["enter"]},
  {"action": "wait", "args": [1.5]}
]

Jarvis ejecuta cada paso, registra resultado, y si funciono guarda como
nueva estrategia en memoria persistente.

Uso:
    from backend.skills.ask_brain import ask_brain_for_plan, execute_plan
    plan = ask_brain_for_plan("abrir Telegram", context={"failed_attempts": [...]})
    result = await execute_plan(plan)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from backend.skills import mouse


SYSTEM_PROMPT = """Eres el cerebro de Jarvis, un asistente de PC Windows.

Cuando Jarvis no logra completar una tarea, te llama y te pasa:
- La tarea que intenta hacer
- Las estrategias que ya probo y fallaron
- El estado actual del sistema (apps abiertas, ventana activa, etc.)

Tu trabajo: devolver UN PLAN JSON con secuencia de acciones que Jarvis ejecuta.

Acciones disponibles (usa exactamente estos nombres):
  - press_keys: tecla(s) a presionar. args=["enter"] o ["ctrl","c"]
  - type_text:  escribir texto. args=["telegram"]
  - click:      click en coordenadas. args=[x, y] o [x, y, "left"|"right"]
  - hover:      mover mouse a coordenadas. args=[x, y]
  - scroll:     scroll. args=[amount] (positivo=up, negativo=down)
  - wait:       esperar segundos. args=[1.5]
  - read_screen: tomar screenshot + OCR. args=[]
  - find_text:  buscar texto en pantalla. args=["Compose"]
  - run_cmd:    ejecutar comando. args=["start", "telegram"]

Reglas:
1. Devuelve SOLO el JSON array. Sin markdown, sin explicaciones.
2. Maximo 8 acciones por plan.
3. Usa wait entre clicks/typewrites para dar tiempo a la UI.
4. Si la tarea requiere ver pantalla, usa read_screen antes de clicks de coordenadas.
5. Si no sabes coordenadas, usa press_keys + type_text en lugar de click.

Ejemplo input:
  Tarea: "abrir Telegram"
  Failed: ["start_menu_search no funciono", "registry no encontro telegram.exe"]

Ejemplo output:
[
  {"action": "press_keys", "args": ["win"]},
  {"action": "wait", "args": [0.6]},
  {"action": "type_text", "args": ["telegram"]},
  {"action": "wait", "args": [0.5]},
  {"action": "press_keys", "args": ["enter"]},
  {"action": "wait", "args": [2]}
]
"""


def ask_brain_for_plan(task: str, context: dict | None = None, timeout: int = 60) -> list[dict]:
    """Llama a Claude CLI con la tarea + contexto. Devuelve plan parseado."""
    claude_bin = shutil.which("claude") or shutil.which("claude.cmd") or "claude"

    user_prompt = (
        f"Tarea: {task}\n"
        f"Contexto: {json.dumps(context or {}, ensure_ascii=False)}\n\n"
        f"Devuelve SOLO el JSON array de acciones."
    )

    sys_file = tempfile.NamedTemporaryFile(
        mode="w", suffix="_brain.md", delete=False, encoding="utf-8"
    )
    sys_file.write(SYSTEM_PROMPT)
    sys_file.close()

    try:
        proc = subprocess.run(
            [
                claude_bin, "-p", user_prompt,
                "--system-prompt-file", sys_file.name,
                "--dangerously-skip-permissions",
                "--model", "claude-sonnet-4-6",
            ],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
    finally:
        try:
            os.unlink(sys_file.name)
        except Exception:
            pass

    if proc.returncode != 0:
        raise RuntimeError(f"ask_brain claude fallo: {proc.stderr[:300]}")

    raw = proc.stdout.strip()
    # Extraer JSON array
    match = re.search(r"\[.*\]", raw, flags=re.DOTALL)
    if not match:
        raise ValueError(f"no encontre JSON array en respuesta: {raw[:200]}")
    return json.loads(match.group(0))


async def execute_plan(plan: list[dict]) -> dict:
    """Ejecuta cada accion del plan. Devuelve log de ejecucion."""
    results = []
    for i, step in enumerate(plan):
        action = step.get("action")
        args = step.get("args", [])
        try:
            if action == "press_keys":
                r = mouse.press_keys(*args)
            elif action == "type_text":
                r = mouse.type_text(args[0])
            elif action == "click":
                r = mouse.click(*args)
            elif action == "hover":
                r = mouse.hover(*args)
            elif action == "scroll":
                r = mouse.scroll(*args)
            elif action == "wait":
                await asyncio.sleep(float(args[0]) if args else 1.0)
                r = {"success": True, "waited": args[0] if args else 1.0}
            elif action == "read_screen":
                from backend.skills import vision
                r = vision.read_screen()
            elif action == "find_text":
                from backend.skills import vision
                r = vision.find_text_position(args[0])
            elif action == "run_cmd":
                proc = subprocess.run(args, capture_output=True, text=True, timeout=15)
                r = {"success": proc.returncode == 0, "stdout": proc.stdout[:300]}
            else:
                r = {"success": False, "error": f"accion desconocida: {action}"}
        except Exception as e:
            r = {"success": False, "error": str(e)}

        r["step"] = i
        r["action"] = action
        results.append(r)

        if not r.get("success") and action not in ("read_screen", "find_text"):
            # Falla critica, abortar plan
            return {"success": False, "results": results, "failed_at_step": i}

    return {"success": True, "results": results}


async def jarvis_handle(task: str, context: dict | None = None) -> dict:
    """Pipeline completo: pregunta a brain + ejecuta plan."""
    try:
        plan = ask_brain_for_plan(task, context)
    except Exception as e:
        return {"success": False, "error": f"brain no respondio: {e}"}
    result = await execute_plan(plan)
    result["plan"] = plan
    result["task"] = task
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python ask_brain.py <tarea>")
        sys.exit(1)
    task = " ".join(sys.argv[1:])
    result = asyncio.run(jarvis_handle(task))
    print(json.dumps(result, ensure_ascii=False, indent=2))
