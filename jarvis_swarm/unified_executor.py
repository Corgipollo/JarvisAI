"""unified_executor.py — Los 2 cerebros viendo en mismo contexto SIEMPRE.

Combina:
  - Cerebro NATIVO (system_brain.json) - sabe shortcuts, paths, comandos shell
  - Cerebro VISION (Claude vision) - ve screenshot + UIA tree de cada paso

Loop cada step:

  1. Cerebro NATIVO propone accion (basado en system_brain.json)
  2. Antes de ejecutar: screenshot ANTES + UIA tree ANTES
  3. EJECUTA via pyautogui
  4. Despues: screenshot DESPUES + UIA tree DESPUES
  5. CEREBRO VISION (Claude) ve los DOS screenshots + delta UIA y juzga:
     - ¿La accion funciono?
     - ¿Hubo efecto inesperado?
     - ¿Siguiente paso?
  6. Si vision dice "OK siguiente" - cerebro nativo propone siguiente
  7. Si vision dice "FALLO" - vision toma control y propone nuevo plan
  8. Estado compartido en data/active_task_state.json (otros agentes leen)

Resultado: native rapidito + vision verifica. Los 2 mismo contexto SIEMPRE.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
STATE_FILE = DATA / "active_task_state.json"
BRAIN_FILE = DATA / "system_brain.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[unified {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def update_state(state: dict):
    """Estado compartido - otros agentes ven que tarea esta activa."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["ts"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str),
                          encoding="utf-8")


def load_brain() -> dict:
    if not BRAIN_FILE.exists():
        return {}
    try:
        return json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def take_screenshot(path: Path) -> bool:
    try:
        import pyautogui
        pyautogui.screenshot(str(path))
        return True
    except Exception:
        return False


def get_uia_summary() -> dict:
    """UIA tree de la ventana activa (sin screenshot)."""
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                if w.is_active():
                    controls = []
                    for c in w.descendants()[:50]:
                        try:
                            text = c.window_text()
                            ctype = str(c.element_info.control_type)
                            if text or ctype in ("Button", "MenuItem"):
                                controls.append({"text": text[:80], "type": ctype})
                        except Exception:
                            continue
                    return {"title": w.window_text(), "controls": controls}
            except Exception:
                continue
    except Exception as e:
        return {"error": str(e)}
    return {}


def cerebro_nativo_propose(task: str, history: list, brain: dict) -> dict | None:
    """Cerebro NATIVO propone accion basado en system_brain."""
    from jarvis_swarm.native_executor import match_native_action
    action = match_native_action(task, brain)
    if action:
        return {"source": "nativo", "action": action}
    # Si nativo no sabe, devuelve None (vision toma control)
    return None


def cerebro_vision_propose_or_verify(task: str, before_path: Path, after_path: Path,
                                      uia_before: dict, uia_after: dict,
                                      last_action: dict | None,
                                      history: list) -> dict | None:
    """Cerebro VISION (Claude) ve los 2 screenshots + delta UIA y decide.

    Si last_action es None: propone primera accion.
    Si last_action existe: evalua si funciono + propone siguiente.
    """
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json, ask_claude_with_image
    except ImportError:
        return None

    # Pedir descripcion del after (vision)
    desc = ""
    if after_path.exists():
        d = ask_claude_with_image(
            f"Tarea: {task}\nUltima accion: {last_action}\n"
            f"¿Que ves en pantalla? Conciso, 2-3 frases.",
            str(after_path), max_tokens=300,
        )
        desc = d or ""

    prompt = (
        f"Eres el cerebro VISION de Jarvis. Tarea actual: {task}\n\n"
        f"Estado anterior (UIA): {json.dumps(uia_before, ensure_ascii=False)[:500]}\n"
        f"Estado actual (UIA): {json.dumps(uia_after, ensure_ascii=False)[:500]}\n"
        f"Ultima accion ejecutada: {last_action}\n"
        f"Descripcion pantalla actual: {desc}\n"
        f"Historial pasos: {[a.get('action') for a in history[-5:]]}\n\n"
        f"Responde JSON con TU veredicto + siguiente paso:\n"
        f'{{"verdict": "OK_PROGRESS|STUCK|DONE|FAILED", '
        f'"reason": "...", '
        f'"next_action": {{"action": "press_key|click|type|hotkey|done|wait", '
        f'"key": "...", "keys": [], "x_pct": 0-100, "y_pct": 0-100, '
        f'"text": "...", "seconds": N}}, '
        f'"confidence": 0-1}}'
    )
    return ask_claude_json(prompt, schema_hint="{verdict,next_action}")


def execute_action(action: dict) -> dict:
    """Ejecuta accion atomica."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        a = (action.get("action") or "").lower()

        if a == "press_key":
            pyautogui.press(action.get("key", ""))
        elif a == "hotkey":
            pyautogui.hotkey(*action.get("keys", []))
        elif a == "type":
            pyautogui.write(action.get("text", ""), interval=0.05)
        elif a == "click":
            import pyautogui as p
            w, h = p.size()
            x = int(w * action.get("x_pct", 50) / 100)
            y = int(h * action.get("y_pct", 50) / 100)
            pyautogui.moveTo(x, y, duration=0.5)
            pyautogui.click()
        elif a == "wait":
            time.sleep(float(action.get("seconds", 1)))
        elif a == "done":
            return {"ok": True, "done": True}
        elif a == "shell":
            import subprocess
            subprocess.Popen(action.get("command", ""), shell=True)
        else:
            return {"ok": False, "error": f"action desconocida: {a}"}
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute_unified(task: str, max_steps: int = 15) -> dict:
    """Loop unificado - ambos cerebros viendo SIEMPRE en mismo contexto."""
    log(f"=== UNIFIED TASK: {task} ===")
    brain = load_brain()
    work_dir = DATA / "unified_runs" / datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir.mkdir(parents=True, exist_ok=True)

    history = []
    update_state({"task": task, "status": "starting", "step": 0})

    # Capture initial state
    initial_shot = work_dir / "step_00_initial.png"
    take_screenshot(initial_shot)
    uia_state = get_uia_summary()

    for step in range(max_steps):
        log(f"--- Step {step+1}/{max_steps} ---")

        # CEREBRO NATIVO propone (rapidito)
        native_proposal = cerebro_nativo_propose(task, history, brain)

        # CEREBRO VISION siempre evalua/propone (tarda mas pero ve)
        before_shot = work_dir / f"step_{step:02d}_before.png"
        take_screenshot(before_shot)
        uia_before = uia_state

        # Si nativo propone con confianza, ejecuta y vision verifica DESPUES
        # Si nativo no sabe, vision propone DESDE EL INICIO
        chosen = None
        if native_proposal:
            log(f"  cerebro NATIVO: {native_proposal['action'].get('name', '?')}")
            chosen = {
                "source": "native",
                "action": {"action": "shell",
                           "command": native_proposal['action'].get('command', '')}
                if native_proposal['action'].get('type') == 'shell_command'
                else {"action": "hotkey",
                      "keys": native_proposal['action'].get('shortcut', '').split('+')}
                if native_proposal['action'].get('type') == 'shortcut'
                else {"action": "wait", "seconds": 0.5},
            }

        last_action = history[-1] if history else None
        vision_decision = cerebro_vision_propose_or_verify(
            task, initial_shot if step == 0 else before_shot, before_shot,
            uia_before, uia_state, last_action, history,
        )

        if vision_decision:
            verdict = vision_decision.get("verdict", "")
            log(f"  cerebro VISION: {verdict} - {vision_decision.get('reason', '')[:80]}")
            if verdict == "DONE":
                update_state({"task": task, "status": "done", "step": step + 1})
                return {"success": True, "task": task, "steps": step + 1,
                        "history": history, "work_dir": str(work_dir)}
            elif verdict == "FAILED":
                update_state({"task": task, "status": "failed", "step": step + 1})
                return {"success": False, "task": task, "steps": step + 1,
                        "history": history, "reason": vision_decision.get("reason")}
            # Si vision NO confia en nativo, o nativo no propuso, vision toma el control
            if not chosen or verdict == "STUCK":
                chosen = {"source": "vision", "action": vision_decision.get("next_action", {})}
                log(f"  vision toma control: {chosen['action'].get('action')}")

        if not chosen:
            log("  ningun cerebro propuso accion, abortando")
            update_state({"task": task, "status": "no_proposal", "step": step})
            return {"success": False, "reason": "no proposal"}

        # Execute
        result = execute_action(chosen["action"])
        action_record = {
            "step": step + 1,
            "source": chosen["source"],
            "action": chosen["action"],
            "result": result,
            "outcome": "OK" if result.get("ok") else f"FAIL: {result.get('error', '')[:50]}",
        }
        history.append(action_record)
        log(f"  [{chosen['source']}] {chosen['action'].get('action')}: {action_record['outcome']}")

        if result.get("done"):
            return {"success": True, "task": task, "steps": step + 1, "history": history}

        update_state({"task": task, "status": "running", "step": step + 1,
                      "last_action": chosen, "last_source": chosen["source"]})

        time.sleep(1)
        uia_state = get_uia_summary()

    update_state({"task": task, "status": "max_steps", "step": max_steps})
    return {"success": False, "reason": "max_steps", "history": history}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python unified_executor.py <tarea>")
        sys.exit(0)
    task = " ".join(sys.argv[1:])
    result = execute_unified(task)
    print(json.dumps({k: v for k, v in result.items() if k != "history"},
                     indent=2, ensure_ascii=False))
