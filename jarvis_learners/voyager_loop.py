"""voyager_loop.py — Coach iterativo Voyager-style.

Loop visible donde Jarvis:
  1. Saca una tarea de gaps.json o task_queue.json
  2. Intenta ejecutarla (pyautogui + Claude vision para ver resultado)
  3. Captura screenshot ANTES y DESPUES
  4. Le pregunta al "coach" (Claude via jarvis_brain):
     "Ejecute esto. Aqui el screenshot antes y despues. ¿Funciono? Si no, ¿que hago diferente?"
  5. Coach responde: "OK funciono, guarda skill" o "Fallo porque X, intenta Y"
  6. Si OK: guarda skill en skill_library
  7. Si FAIL: vuelve a paso 2 con nueva estrategia del coach (max 3 intentos)
  8. Loguea TODO a data/voyager_log.jsonl

Asi Emmanuel ve mouse moverse + apps abriendose + coach decidiendo en log.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOG = DATA / "voyager_log.jsonl"
SKILL_DIR = DATA / "skill_library"
GAPS = DATA / "gaps.json"
TICK_SECONDS = 30  # entre tareas, da tiempo a ver lo que pasa

sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def now_iso() -> str:
    return datetime.now().isoformat()


def banner(msg: str):
    line = "=" * 70
    print(f"\n{line}\n  [voyager {datetime.now().strftime('%H:%M:%S')}] {msg}\n{line}\n", flush=True)


def log_event(event: dict):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")


def take_screenshot(out_path: Path) -> bool:
    try:
        import pyautogui
        pyautogui.screenshot(str(out_path))
        return True
    except Exception as e:
        print(f"  ERR screenshot: {e}")
        return False


def execute_action_step(step: dict) -> dict:
    """Ejecuta un paso atomico del plan. Retorna resultado.

    Step formato (lo decide Claude):
      {"action": "press_key", "key": "win"}
      {"action": "type", "text": "telegram"}
      {"action": "wait", "seconds": 2}
      {"action": "move_mouse", "x": 500, "y": 300}
      {"action": "click", "button": "left"}
      {"action": "screenshot"}
    """
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
    except ImportError:
        return {"ok": False, "error": "pyautogui no disponible"}

    a = step.get("action", "").lower()
    try:
        if a == "press_key":
            pyautogui.press(step["key"])
        elif a == "type":
            pyautogui.write(step["text"], interval=0.08)
        elif a == "wait":
            time.sleep(float(step.get("seconds", 1)))
        elif a == "move_mouse":
            pyautogui.moveTo(step["x"], step["y"], duration=1.0)
        elif a == "click":
            pyautogui.click(button=step.get("button", "left"))
        elif a == "screenshot":
            pass  # se maneja afuera
        elif a == "hotkey":
            keys = step.get("keys", [])
            pyautogui.hotkey(*keys)
        else:
            return {"ok": False, "error": f"action desconocida: {a}"}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def ask_coach_for_plan(task: str, previous_attempts: list[dict] | None = None) -> list[dict] | None:
    """Pide al coach (Claude) un plan de pasos para esta tarea."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
    except ImportError:
        return None

    history = ""
    if previous_attempts:
        history = "\n\nINTENTOS PREVIOS QUE FALLARON:\n" + "\n".join(
            f"- {a.get('task')}: {a.get('result', {}).get('verdict', '?')}, "
            f"feedback: {a.get('coach_feedback', '')[:200]}"
            for a in previous_attempts[-3:]
        )

    prompt = (
        f"Eres el COACH de Jarvis (asistente Windows en VM). Tarea actual:\n"
        f"  {task}\n"
        f"{history}\n\n"
        f"Genera un plan de pasos atomicos para ejecutar en Windows 11 via pyautogui.\n"
        f"Responde JSON estricto:\n"
        f'{{"plan": [\n'
        f'  {{"action": "press_key", "key": "win"}},\n'
        f'  {{"action": "wait", "seconds": 1}},\n'
        f'  {{"action": "type", "text": "telegram"}},\n'
        f'  {{"action": "wait", "seconds": 1}},\n'
        f'  {{"action": "press_key", "key": "enter"}}\n'
        f'], "expected_result": "se abre la app X en pantalla"}}\n\n'
        f"Acciones disponibles: press_key, type, wait, move_mouse, click, hotkey.\n"
        f"Maximo 10 pasos. Que sean ROBUSTOS (esperas entre acciones)."
    )
    plan = ask_claude_json(prompt)
    if plan and "plan" in plan:
        return plan["plan"]
    return None


def ask_coach_verdict(task: str, before_img: Path, after_img: Path, expected: str) -> dict:
    """Pide al coach que VEA los screenshots y diga si la tarea funciono."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image, ask_claude_json
    except ImportError:
        return {"verdict": "unknown", "reason": "jarvis_brain no disponible"}

    # Primero descripcion del estado actual
    description = ask_claude_with_image(
        f"Tarea ejecutada: {task}\nResultado esperado: {expected}\n\n"
        f"¿Que ves en pantalla? Describe brevemente.",
        after_img,
        max_tokens=300,
    )
    if not description:
        return {"verdict": "unknown", "reason": "no pude obtener descripcion"}

    # Despues veredicto
    prompt = (
        f"Tarea: {task}\n"
        f"Esperado: {expected}\n"
        f"Lo que vio Claude en pantalla DESPUES: {description}\n\n"
        f"Responde JSON: "
        f'{{"verdict": "OK" o "FAIL", "reason": "explicacion corta", '
        f'"next_strategy": "si FAIL, que probar diferente"}}'
    )
    res = ask_claude_json(prompt) or {}
    res["description"] = description
    return res


def attempt_task(task: str, max_retries: int = 3) -> dict:
    """Intenta una tarea hasta max_retries veces con feedback del coach."""
    banner(f"TASK: {task}")
    attempts = []

    for attempt_n in range(1, max_retries + 1):
        print(f"\n  Intento {attempt_n}/{max_retries}", flush=True)

        # 1. Coach genera plan
        plan = ask_coach_for_plan(task, previous_attempts=attempts)
        if not plan:
            print("  coach no devolvio plan", flush=True)
            return {"task": task, "success": False, "reason": "no plan"}
        print(f"  plan: {len(plan)} pasos", flush=True)

        # 2. Screenshot antes
        attempt_dir = DATA / "voyager_attempts" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{attempt_n}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        before = attempt_dir / "before.png"
        take_screenshot(before)

        # 3. Ejecutar plan
        step_results = []
        for i, step in enumerate(plan):
            r = execute_action_step(step)
            step_results.append({"step": step, "result": r})
            print(f"    [{i+1}] {step.get('action')}: {'OK' if r['ok'] else r.get('error', '')}", flush=True)
            time.sleep(0.5)

        time.sleep(2)  # darle tiempo al sistema
        after = attempt_dir / "after.png"
        take_screenshot(after)

        # 4. Coach evalua
        expected = "se abre/cambia la pantalla segun la tarea"
        verdict = ask_coach_verdict(task, before, after, expected)
        print(f"  coach: {verdict.get('verdict', '?')} - {verdict.get('reason', '')[:80]}", flush=True)

        # 5. Log
        event = {
            "ts": now_iso(),
            "task": task,
            "attempt": attempt_n,
            "plan": plan,
            "step_results": step_results,
            "before": str(before),
            "after": str(after),
            "verdict": verdict,
            "coach_feedback": verdict.get("next_strategy", ""),
        }
        log_event(event)
        attempts.append(event)

        if verdict.get("verdict", "").upper() == "OK":
            # Guardar como skill
            save_skill(task, plan, attempts)
            return {"task": task, "success": True, "attempts": len(attempts), "plan": plan}

    return {"task": task, "success": False, "attempts": max_retries}


def save_skill(task: str, plan: list[dict], attempts: list[dict]):
    SKILL_DIR.mkdir(parents=True, exist_ok=True)
    skill_id = task.lower().replace(" ", "_")[:50]
    skill_file = SKILL_DIR / f"{skill_id}.json"
    skill = {
        "id": skill_id,
        "name": task,
        "plan": plan,
        "learned_via": "voyager_loop",
        "attempts_to_learn": len(attempts),
        "confidence": min(1.0, 1.0 / len(attempts)),
        "created": now_iso(),
    }
    skill_file.write_text(json.dumps(skill, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  SKILL guardado: {skill_file.name}", flush=True)


def main():
    banner("voyager_loop iniciado")

    while True:
        # Sacar siguiente tarea
        if not GAPS.exists():
            print("  no hay gaps.json, esperando...", flush=True)
            time.sleep(60)
            continue
        try:
            data = json.loads(GAPS.read_text(encoding="utf-8"))
            queries = data.get("queries", [])
        except Exception:
            queries = []

        if not queries:
            print("  no hay queries pendientes, esperando 5min...", flush=True)
            time.sleep(300)
            continue

        task = queries[0]

        # Verificar si ya tenemos esa skill
        skill_id = task.lower().replace(" ", "_")[:50]
        if (SKILL_DIR / f"{skill_id}.json").exists():
            print(f"  skill ya existe, quitando '{task}' de gaps", flush=True)
            data["queries"] = queries[1:]
            GAPS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            continue

        # Ejecutar
        result = attempt_task(task)

        # Sacar de gaps si funciono o agotamos retries
        data["queries"] = queries[1:]
        GAPS.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"\n  result: {result['success']} (intentos: {result.get('attempts', 1)})", flush=True)
        print(f"  durmiendo {TICK_SECONDS}s antes de siguiente tarea...", flush=True)
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "once":
        # Modo prueba: una sola tarea pasada por args
        task = " ".join(sys.argv[2:]) or "abre Notepad y escribe hola"
        result = attempt_task(task)
        print(json.dumps(result, indent=2, default=str))
    else:
        main()
