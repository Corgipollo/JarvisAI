"""vision_executor.py — Loop ver-pensar-actuar con Claude vision continuo.

Para tareas complejas tipo "edita este video en CapCut" o "envia mensaje WhatsApp":

  while not done:
    1. Screenshot de la pantalla
    2. Manda a Claude (con la tarea original + history acciones)
    3. Claude responde JSON: {action: click/type/key, target: ..., reason: ..., done: false}
    4. Ejecuta accion con pyautogui
    5. Sleep 1s (que la UI actualice)
    6. Loop hasta que Claude diga {done: true} o max_steps

Como un humano con super reflejos: ve, piensa, hace, repite.

API:
    from jarvis_swarm.vision_executor import execute_task

    result = execute_task("abre CapCut e importa un video del Desktop")
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
EXECUTIONS_DIR = DATA / "vision_executions"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[vision_executor {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def take_screenshot(path: Path) -> bool:
    try:
        import pyautogui
        pyautogui.screenshot(str(path))
        return True
    except Exception as e:
        log(f"  screenshot fallo: {e}")
        return False


def ask_claude_next_action(task: str, screenshot_path: Path, history: list[dict],
                            relevant_skills: list[dict] | None = None) -> dict | None:
    """Mandar screenshot + tarea + history a Claude. Retorna proxima accion JSON."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
    except ImportError:
        return None

    history_text = ""
    if history:
        last = history[-5:]
        history_text = "\n=== ACCIONES PREVIAS ===\n" + "\n".join(
            f"{i+1}. {a.get('action', '?')}({a.get('target', '')}) -> {a.get('outcome', '?')}"
            for i, a in enumerate(last)
        )

    skills_text = ""
    if relevant_skills:
        skills_text = "\n=== SKILLS RELEVANTES APRENDIDAS ===\n" + "\n".join(
            f"- {s.get('name', '?')}: {s.get('intent', '')[:100]}"
            for s in relevant_skills[:5]
        )

    prompt = (
        f"Tarea actual: {task}\n"
        f"{skills_text}\n"
        f"{history_text}\n\n"
        f"VES la pantalla actual. Decide la SIGUIENTE accion atomica para avanzar.\n\n"
        f"Acciones disponibles:\n"
        f"- click: requiere x_pct, y_pct (porcentaje 0-100)\n"
        f"- type: requiere text\n"
        f"- press_key: requiere key (enter, tab, esc, win, ctrl+s, etc)\n"
        f"- hotkey: requiere keys (lista, ej [ctrl,c])\n"
        f"- wait: requiere seconds\n"
        f"- scroll: requiere amount (negativo abajo, positivo arriba)\n"
        f"- open_app: requiere target (nombre app, abre con Win+R)\n"
        f"- done: tarea completada\n\n"
        f"Responde JSON ESTRICTO (sin markdown, sin texto extra):\n"
        f'{{"action": "click|type|press_key|hotkey|wait|scroll|open_app|done", '
        f'"x_pct": 0-100, "y_pct": 0-100, "text": "...", "key": "...", '
        f'"keys": [...], "seconds": N, "amount": N, "target": "...", '
        f'"reason": "por que esta accion", "expected_outcome": "que espero ver", '
        f'"done": false}}\n\n'
        f"IMPORTANTE: si la tarea ya esta completa, responde {{\"action\": \"done\", \"done\": true}}.\n"
        f"NO inventes acciones. Si no sabes que hacer, responde {{\"action\": \"wait\", \"seconds\": 2}}."
    )

    text = ask_claude_with_image(prompt, str(screenshot_path), max_tokens=1000)
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def execute_action(action: dict) -> dict:
    """Ejecuta una accion atomica con pyautogui."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
    except ImportError:
        return {"ok": False, "error": "pyautogui no disponible"}

    a = (action.get("action") or "").lower()
    try:
        if a == "click":
            w, h = pyautogui.size()
            x = int(w * action.get("x_pct", 50) / 100)
            y = int(h * action.get("y_pct", 50) / 100)
            pyautogui.moveTo(x, y, duration=0.6)
            time.sleep(0.2)
            pyautogui.click()
        elif a == "type":
            pyautogui.write(action.get("text", ""), interval=0.05)
        elif a == "press_key":
            pyautogui.press(action.get("key", ""))
        elif a == "hotkey":
            pyautogui.hotkey(*action.get("keys", []))
        elif a == "wait":
            time.sleep(float(action.get("seconds", 1)))
        elif a == "scroll":
            pyautogui.scroll(int(action.get("amount", -200)))
        elif a == "open_app":
            target = action.get("target", "")
            pyautogui.hotkey("win", "r")
            time.sleep(1)
            pyautogui.write(target, interval=0.05)
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(2)
        elif a == "done":
            return {"ok": True, "done": True}
        else:
            return {"ok": False, "error": f"action desconocida: {a}"}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def find_relevant_skills(task: str, top_k: int = 5) -> list[dict]:
    """Encuentra skills aprendidas relacionadas con la tarea."""
    skill_dir = DATA / "skill_library"
    if not skill_dir.exists():
        return []
    task_words = set(task.lower().split())
    matches = []
    for f in skill_dir.glob("*.json"):
        if f.name.startswith("_"):
            continue
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            name = (s.get("name", "") + " " + s.get("intent", "")).lower()
            score = sum(1 for w in task_words if w in name)
            if score > 0:
                matches.append((score, s))
        except Exception:
            continue
    matches.sort(key=lambda x: -x[0])
    return [m[1] for m in matches[:top_k]]


def execute_task(task: str, max_steps: int = 20) -> dict:
    """Loop principal ver-pensar-actuar hasta done o max_steps."""
    log(f"=== TASK: {task} ===")
    work_dir = EXECUTIONS_DIR / datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir.mkdir(parents=True, exist_ok=True)

    relevant_skills = find_relevant_skills(task)
    log(f"  skills relevantes: {len(relevant_skills)}")

    history = []
    for step in range(max_steps):
        log(f"\n--- Step {step+1}/{max_steps} ---")
        shot = work_dir / f"step_{step:02d}.png"
        if not take_screenshot(shot):
            return {"success": False, "error": "screenshot fail", "steps": step}

        action = ask_claude_next_action(task, shot, history, relevant_skills)
        if not action:
            log("  claude no respondio")
            return {"success": False, "error": "claude no respondio", "steps": step}

        log(f"  accion: {action.get('action')} - {action.get('reason', '')[:80]}")

        if action.get("done") or action.get("action") == "done":
            log("  CLAUDE dice DONE")
            return {"success": True, "task": task, "steps": step + 1,
                    "history": history, "work_dir": str(work_dir)}

        result = execute_action(action)
        action["outcome"] = "OK" if result["ok"] else f"FAIL: {result.get('error', '')[:50]}"
        history.append(action)
        time.sleep(1)  # dar tiempo a UI

    log("  max_steps alcanzado sin done")
    return {"success": False, "error": "max_steps", "steps": max_steps,
            "history": history, "work_dir": str(work_dir)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python vision_executor.py 'tarea a ejecutar'")
        print('Ejemplo: python vision_executor.py "abre Notepad y escribe Hola Emmanuel"')
        sys.exit(0)
    task = " ".join(sys.argv[1:])
    result = execute_task(task)
    print(json.dumps({k: v for k, v in result.items() if k != "history"},
                     indent=2, ensure_ascii=False))
