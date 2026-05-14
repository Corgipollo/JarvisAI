"""screen_awareness.py — Jarvis SIEMPRE sabe que hay en pantalla.

Loop continuo cada 5 segundos:
  1. Screenshot completo
  2. UIA tree de la ventana activa (estructura nativa)
  3. OCR rapido (Tesseract) sobre texto visible
  4. Lista de procesos activos (foreground)
  5. Detecta CAMBIOS: nueva ventana abierta, app cambio, texto nuevo
  6. Actualiza data/screen_state.json (state actual, siempre live)
  7. Si hay cambio significativo, mete evento en data/screen_events.jsonl
  8. Cada 60 seg: pide a Claude vision una descripcion rica del contexto
     ('estas en CapCut timeline editando intro', 'estas en escritorio idle', etc)
     y la guarda en screen_state.json para que otros agentes la lean.

Otros agentes (vision_executor, auto_practice, error_resolver) leen screen_state.json
para saber INSTANTE que hay en pantalla sin tomar screenshot ellos mismos.

Es como la 'visi perif' de un humano: constante, en background, barato.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
STATE_FILE = DATA / "screen_state.json"
EVENTS_FILE = DATA / "screen_events.jsonl"
SHOT_CURRENT = DATA / "screen_current.png"

TICK_FAST = 5     # screenshot + UIA cada 5s
TICK_CLAUDE = 60  # description rica via Claude cada 60s

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[screen_awareness {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def take_shot() -> bool:
    try:
        import pyautogui
        DATA.mkdir(parents=True, exist_ok=True)
        pyautogui.screenshot(str(SHOT_CURRENT))
        return True
    except Exception as e:
        log(f"  shot fail: {e}")
        return False


def get_active_window_info() -> dict:
    """Info de la ventana activa via pywinauto."""
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                if w.is_active():
                    controls = []
                    try:
                        for c in w.descendants()[:25]:
                            try:
                                t = c.window_text()
                                if t:
                                    controls.append({
                                        "text": t[:80],
                                        "type": str(c.element_info.control_type),
                                    })
                            except Exception:
                                continue
                    except Exception:
                        pass
                    return {
                        "title": w.window_text()[:200],
                        "class": w.class_name()[:100],
                        "controls": controls[:25],
                    }
            except Exception:
                continue
    except ImportError:
        return {"error": "pywinauto no instalado"}
    except Exception as e:
        return {"error": str(e)}
    return {}


def list_foreground_processes() -> list[str]:
    """Lista de procesos con ventana visible."""
    try:
        import psutil
        procs = []
        for p in psutil.process_iter(["pid", "name"]):
            try:
                name = p.info.get("name", "")
                if name and name not in procs:
                    procs.append(name)
            except Exception:
                continue
        return procs[:50]
    except ImportError:
        return []


def quick_ocr(shot_path: Path) -> str:
    """OCR rapido sobre el screenshot."""
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(shot_path), lang="spa+eng")
        # Quitar lineas vacias y limitar
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        return "\n".join(lines)[:1500]
    except Exception:
        return ""


def hash_image(path: Path) -> str:
    """Hash del screenshot para detectar cambios."""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()[:16]
    except Exception:
        return ""


def ask_claude_for_context_description(shot_path: Path, state: dict) -> str | None:
    """Cada N seg pide a Claude descripcion rica."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
    except ImportError:
        return None
    prompt = (
        f"Eres el modulo de SCREEN AWARENESS de Jarvis. "
        f"Mira el screenshot. La ventana activa es: {state.get('active_window', {}).get('title', '?')}\n\n"
        f"En 2-3 frases describe el contexto actual: que app esta abierta, "
        f"que hace el usuario, en que parte de la app. "
        f"Como si fueras los ojos perifericos de un humano que da contexto "
        f"a la cabeza. Conciso, util, accionable."
    )
    return ask_claude_with_image(prompt, str(shot_path), max_tokens=300)


def write_state(state: dict):
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str),
                              encoding="utf-8")
    except Exception as e:
        log(f"  write_state fail: {e}")


def emit_event(event: dict):
    try:
        EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with EVENTS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now().isoformat(), **event},
                               ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def main():
    log("awareness iniciado - tick 5s fast, 60s claude")
    last_hash = ""
    last_window_title = ""
    last_claude_call = 0
    last_description = ""

    while True:
        try:
            if not take_shot():
                time.sleep(TICK_FAST)
                continue

            # Hash para detectar cambio visual
            curr_hash = hash_image(SHOT_CURRENT)
            changed = curr_hash != last_hash

            # Info ventana activa
            active = get_active_window_info()
            window_title = active.get("title", "")

            # Detect window switch
            if window_title and window_title != last_window_title:
                emit_event({"type": "window_switch",
                            "from": last_window_title, "to": window_title})
                log(f"  window switch: {last_window_title[:30]} -> {window_title[:30]}")
                last_window_title = window_title

            # OCR + procesos (mas barato que Claude)
            ocr_text = quick_ocr(SHOT_CURRENT) if changed else ""
            procs = list_foreground_processes() if changed else []

            # Descripcion rica cada 60s
            now = time.time()
            description = last_description
            if changed and (now - last_claude_call) > TICK_CLAUDE:
                state_partial = {"active_window": active}
                desc = ask_claude_for_context_description(SHOT_CURRENT, state_partial)
                if desc:
                    description = desc
                    last_description = desc
                    last_claude_call = now
                    log(f"  contexto: {desc[:100]}")

            # Update state completo
            state = {
                "ts": datetime.now().isoformat(),
                "screenshot": str(SHOT_CURRENT),
                "image_hash": curr_hash,
                "changed_since_last": changed,
                "active_window": active,
                "ocr_text": ocr_text[:1000],
                "foreground_processes": procs[:20],
                "context_description": description,
            }
            write_state(state)

            last_hash = curr_hash
        except KeyboardInterrupt:
            log("detenido")
            break
        except Exception as e:
            log(f"  ERR tick: {e}")
        time.sleep(TICK_FAST)


if __name__ == "__main__":
    main()
