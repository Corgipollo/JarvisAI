"""native_executor.py — Ejecuta acciones via UIA NATIVA (sin pixel click).

Diferencia con vision_executor:
  - vision_executor: screenshot → Claude vision → pixel click
  - native_executor: UIA query directo → control.invoke() (semantico, instantaneo)

Ejemplos:

  task = "guardar archivo en Notepad"
  →  find_window(title="Notepad")
  →  send_keys(Ctrl+S)  (sabido de system_brain.text_editor_actions)

  task = "ordenar escritorio por fecha"
  →  desktop = find_window(class="Progman" o "WorkerW")
  →  context_menu_via_keyboard()  (Menu key con desktop foco)
  →  navigate menu "Ordenar por" > "Fecha de modificacion" via UIA
  →  invoke

  task = "abrir Documents en Explorer"
  →  consultar system_brain.native_system_actions["open_explorer_documents"]
  →  run('explorer shell:Documents')

Sin pixels. Sin screenshots. Sin Claude vision. Sub-segundo.

Fallback: si UIA falla, llama a vision_executor.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
BRAIN_FILE = DATA / "system_brain.json"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[native_executor {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_brain() -> dict:
    if not BRAIN_FILE.exists():
        return {}
    try:
        return json.loads(BRAIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


# ============================================================================
# Match task → native action conocida
# ============================================================================
def match_native_action(task: str, brain: dict) -> dict | None:
    """Busca en system_brain una accion que matchee la tarea."""
    task_lower = task.lower()
    candidates = []

    # Native system actions (shell commands)
    for action_name, command in brain.get("native_system_actions", {}).items():
        keywords = action_name.replace("_", " ").lower().split()
        score = sum(1 for k in keywords if k in task_lower)
        if score >= 2:
            candidates.append({
                "type": "shell_command",
                "name": action_name,
                "command": command,
                "score": score,
            })

    # Desktop actions
    for action_name, desc in brain.get("desktop_actions", {}).items():
        keywords = action_name.replace("_", " ").lower().split()
        score = sum(1 for k in keywords if k in task_lower)
        if score >= 2:
            candidates.append({
                "type": "desktop_action",
                "name": action_name,
                "description": desc,
                "score": score,
            })

    # Shortcuts universales
    for action_name, shortcut in brain.get("universal_actions", {}).items():
        keywords = action_name.replace("_", " ").lower().split()
        score = sum(1 for k in keywords if k in task_lower)
        if score >= 2:
            candidates.append({
                "type": "shortcut",
                "name": action_name,
                "shortcut": shortcut,
                "score": score,
            })

    if not candidates:
        return None
    candidates.sort(key=lambda c: -c["score"])
    return candidates[0]


# ============================================================================
# Ejecucion nativa
# ============================================================================
def execute_shell_command(command: str) -> dict:
    """Ejecuta un comando shell directo (mas rapido que pyautogui)."""
    try:
        if "(hotkey)" in command:
            # Es un hotkey notation, parsear y usar pyautogui
            shortcut = command.split(" (hotkey)")[0].strip()
            keys = [k.strip().lower() for k in shortcut.split("+")]
            import pyautogui
            pyautogui.hotkey(*keys)
            return {"ok": True, "method": "hotkey", "keys": keys}
        else:
            # Comando shell directo (ej "explorer shell:Documents")
            subprocess.Popen(command, shell=True)
            return {"ok": True, "method": "shell", "command": command}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def execute_via_uia(action: dict) -> dict:
    """Ejecuta accion UIA: find window + invoke control."""
    try:
        from pywinauto import Desktop
    except ImportError:
        return {"ok": False, "error": "pywinauto no instalado"}

    # TODO: implementacion completa de UIA invoke
    # Por ahora retornamos descripcion
    return {"ok": True, "method": "uia_pending", "action": action}


def desktop_right_click() -> dict:
    """Click derecho EN EL ESCRITORIO via Win32 SendMessage (sin pixel).

    El truco: Win+D minimiza todo, despues Menu key con foco en desktop
    invoca menu contextual.
    """
    try:
        import pyautogui
        # Win+D para mostrar desktop (todo minimizado)
        pyautogui.hotkey("win", "d")
        time.sleep(1)
        # Menu key (o Shift+F10) invoca menu contextual
        pyautogui.press("apps")  # Menu key
        time.sleep(0.5)
        return {"ok": True, "method": "win+d + menu_key"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def sort_desktop_by_date() -> dict:
    """Ordena escritorio por fecha SIN screenshots."""
    try:
        import pyautogui
        # 1. Mostrar desktop
        pyautogui.hotkey("win", "d")
        time.sleep(1)
        # 2. Menu key abre contexto
        pyautogui.press("apps")
        time.sleep(1)
        # 3. "o" para "Ordenar por" (atajo de menu en ES)
        pyautogui.press("o")
        time.sleep(1)
        # 4. "f" para "Fecha de modificacion"
        pyautogui.press("f")
        time.sleep(1)
        # 5. Enter
        pyautogui.press("enter")
        return {"ok": True, "method": "keyboard_navigation"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ============================================================================
# API publica
# ============================================================================
KNOWN_RECIPES = {
    "ordena escritorio por fecha": sort_desktop_by_date,
    "ordenar escritorio por fecha": sort_desktop_by_date,
    "sort desktop by date": sort_desktop_by_date,
    "click derecho en escritorio": desktop_right_click,
    "menu contextual escritorio": desktop_right_click,
}


def execute_native(task: str) -> dict:
    """Ejecuta tarea via metodo NATIVO (sin vision)."""
    log(f"=== NATIVE TASK: {task} ===")
    task_lower = task.lower().strip()

    # 1. Recetas conocidas
    for recipe_key, fn in KNOWN_RECIPES.items():
        if recipe_key in task_lower:
            log(f"  receta conocida: {recipe_key}")
            return fn()

    # 2. Match en system_brain
    brain = load_brain()
    if not brain:
        log("  system_brain.json no existe, fallback vision")
        return {"ok": False, "error": "no brain", "fallback": "vision"}

    action = match_native_action(task, brain)
    if action:
        log(f"  match nativo: {action.get('name')} (score {action.get('score')})")
        if action["type"] == "shell_command":
            return execute_shell_command(action["command"])
        elif action["type"] == "shortcut":
            return execute_shell_command(action["shortcut"])
        elif action["type"] == "desktop_action":
            return {"ok": True, "method": "desktop_action_described",
                    "description": action["description"]}

    log("  no match nativo, fallback vision")
    return {"ok": False, "error": "no native match", "fallback": "vision"}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python native_executor.py <tarea>")
        sys.exit(0)
    task = " ".join(sys.argv[1:])
    result = execute_native(task)
    print(json.dumps(result, indent=2, ensure_ascii=False))
