"""youtube_transcript_skill.py - Skill REAL: Jarvis usa browser + mouse para buscar
YouTube y extraer transcripcion. Es DOS cosas en una:
  1) Practica de mouse en escenario real (cada click es entrenamiento)
  2) Extraccion de transcript via UI (no via API)

Flow:
  1. Abre Chrome via shell (skill segura)
  2. Ctrl+L para enfocar URL bar
  3. Type youtube.com/results?search_query={query} + Enter
  4. Espera, screenshot, Claude vision dice "donde esta el primer resultado"
  5. Click ahi
  6. Espera load del video
  7. Scroll hacia abajo, busca boton "Mostrar transcripcion" via UIA/vision
  8. Click
  9. Espera panel, lee transcripcion via UIA (texto plano)
  10. Devuelve transcript

Cada paso es loggeado a swarm_memory para que otros brains aprendan del patron.
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
LOG = DATA / "youtube_skill.log"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    line = f"[yt_skill {datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def open_chrome():
    """Abre Chrome (skill segura, ya conocida)."""
    log("paso 1: abriendo Chrome")
    try:
        subprocess.Popen(["cmd", "/c", "start", "chrome"], shell=False)
        time.sleep(5)
        return True
    except Exception as e:
        log(f"  fallo abrir chrome: {e}")
        return False


def focus_url_bar_and_search(query: str):
    """Ctrl+L para enfocar URL bar y navega directo a resultados YouTube."""
    log(f"paso 2: navegando YouTube con query='{query}'")
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        # Ctrl+L = focus address bar
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.5)
        # Type direct YouTube search URL (skip search-on-google)
        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        pyautogui.write(url, interval=0.02)
        time.sleep(0.3)
        pyautogui.press("enter")
        time.sleep(6)  # Wait for page load
        return True
    except Exception as e:
        log(f"  fallo navegar: {e}")
        return False


def find_first_video_with_vision() -> tuple[int, int] | None:
    """Localiza primer video. Tier 1: UI-TARS (rapido+preciso). Tier 2: Claude vision."""
    log("paso 3: localizando primer video")
    try:
        import pyautogui
        shot = DATA / "youtube_search_shot.png"
        pyautogui.screenshot(str(shot))
    except Exception as e:
        log(f"  screenshot fallo: {e}")
        return None

    # Tier 1: UI-TARS (host RTX 3050)
    try:
        from jarvis_swarm.ui_tars_client import predict_click_uitars, is_uitars_available
        if is_uitars_available():
            coords = predict_click_uitars(str(shot),
                                          "click on the first video result thumbnail (not an ad)")
            if coords:
                log(f"  UI-TARS coords: {coords}")
                return coords
    except Exception as e:
        log(f"  UI-TARS fail: {e}")

    # Tier 2: Claude vision fallback
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
        prompt = (
            "Esta es una pagina de resultados de YouTube. Donde esta el PRIMER video "
            "(no anuncio)? Devuelve JSON con coordenadas como porcentaje del centro del "
            "thumbnail del primer video real:\n"
            '{"x_pct": 0-100, "y_pct": 0-100, "found": true|false}\n'
            "SOLO el JSON."
        )
        resp = ask_claude_with_image(prompt, str(shot), max_tokens=200)
        import re
        m = re.search(r"\{.*\}", resp or "", flags=re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if not data.get("found"):
            return None
        screen_w, screen_h = pyautogui.size()
        x = int(screen_w * data["x_pct"] / 100)
        y = int(screen_h * data["y_pct"] / 100)
        log(f"  Claude vision coords: ({x}, {y})")
        return (x, y)
    except Exception as e:
        log(f"  Claude vision fallo: {e}")
        return None


def click_at(x: int, y: int):
    """Click en coordenadas + practica de mouse REAL."""
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.moveTo(x, y, duration=0.8)
    pyautogui.click()
    time.sleep(0.3)


def find_transcript_button() -> tuple[int, int] | None:
    """Busca boton 'Mostrar transcripcion' en pagina del video.
    Primero scroll hacia abajo, luego vision."""
    log("paso 5: buscando boton transcripcion")
    try:
        import pyautogui
        pyautogui.FAILSAFE = False
        # Scroll down para revelar boton (no esta on-screen al cargar video)
        for _ in range(3):
            pyautogui.scroll(-5)
            time.sleep(0.5)
        time.sleep(1)

        shot = DATA / "youtube_video_shot.png"
        pyautogui.screenshot(str(shot))

        from jarvis_bridge.jarvis_brain import ask_claude_with_image
        prompt = (
            "Esto es una pagina de YouTube viendo un video. Donde esta el boton "
            "'Mostrar transcripcion' (o 'Show transcript')? Suele estar abajo de la "
            "descripcion. Devuelve JSON:\n"
            '{"x_pct": 0-100, "y_pct": 0-100, "found": true|false, "label_seen": "..."}\n'
            "Si no lo ves, prueba hacer scroll mental hacia 'mas' o '...' para "
            "expandir descripcion. SOLO JSON."
        )
        resp = ask_claude_with_image(prompt, str(shot), max_tokens=300)
        import re
        m = re.search(r"\{.*\}", resp or "", flags=re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(0))
        if not data.get("found"):
            log(f"  no encontrado. Visto: {data.get('label_seen', '?')}")
            return None
        screen_w, screen_h = pyautogui.size()
        x = int(screen_w * data["x_pct"] / 100)
        y = int(screen_h * data["y_pct"] / 100)
        log(f"  boton transcripcion en ({x}, {y})")
        return (x, y)
    except Exception as e:
        log(f"  fallo busqueda transcripcion: {e}")
        return None


def extract_transcript_text() -> str:
    """Lee panel de transcripcion via UIA (texto puro)."""
    log("paso 6: extrayendo texto del panel")
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        for w in desktop.windows():
            try:
                if "Chrome" not in w.window_text() and "Edge" not in w.window_text():
                    continue
                # Walk descendants for Transcript panel
                texts = []
                for c in w.descendants()[:500]:
                    try:
                        t = c.window_text() or ""
                        if t and len(t) > 5 and len(t) < 200:
                            # Skip nav, button, generic
                            if any(k in t.lower() for k in [
                                "subscribe", "share", "save", "like", "search",
                                "settings", "playlist", "playback"
                            ]):
                                continue
                            texts.append(t)
                    except Exception:
                        continue
                if texts:
                    return "\n".join(texts)
            except Exception:
                continue
    except Exception as e:
        log(f"  UIA extract fallo: {e}")
    return ""


def practice_youtube_transcript_skill(query: str = "windows file explorer tutorial") -> dict:
    """Skill end-to-end. Cada step es practica de mouse + busqueda real."""
    log(f"=== SKILL: YouTube transcript extraction === query='{query}'")
    result = {"query": query, "ts": datetime.now().isoformat(), "steps": []}

    if not open_chrome():
        result["error"] = "open_chrome_failed"
        return result
    result["steps"].append("chrome_opened")

    if not focus_url_bar_and_search(query):
        result["error"] = "navigate_failed"
        return result
    result["steps"].append("navigated_yt_results")

    coords = find_first_video_with_vision()
    if not coords:
        result["error"] = "no_first_video_found"
        return result
    click_at(*coords)
    result["steps"].append("clicked_first_video")
    log("paso 4: cargando video, esperando 5s")
    time.sleep(5)

    tbtn = find_transcript_button()
    if tbtn:
        click_at(*tbtn)
        time.sleep(2)
        result["steps"].append("clicked_transcript_button")
        text = extract_transcript_text()
        if text:
            result["transcript_chars"] = len(text)
            result["transcript_preview"] = text[:500]
            result["steps"].append("extracted_text")
            log(f"  OK extracted {len(text)} chars")
            # Save full transcript
            tf = DATA / f"transcript_{int(time.time())}.txt"
            tf.write_text(text, encoding="utf-8")
            result["transcript_file"] = str(tf)
        else:
            result["error"] = "extract_empty"
    else:
        result["error"] = "no_transcript_button"

    return result


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "windows file explorer tutorial"
    r = practice_youtube_transcript_skill(q)
    print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
