"""dialog_guardian.py — Vigia 24/7 que detecta dialogs/popups y los resuelve.

Cierra el gap mas obvio del Jarvis: cuando un dialog modal aparece (crash de
una app, error de Windows, popup de PowerToys, "Activar Windows", etc.), el
sistema no puede continuar porque el foco queda atrapado.

Loop:
  1. Cada 20 seg toma screenshot completo
  2. Heuristica: detecta si hay un dialog box visible (ventana centrada chica
     con boton tipo 'Aceptar'/'OK'/'Cerrar'/'Cancel'/'Ignorar')
  3. Si detecta: pregunta a Claude vision via jarvis_brain.ask_claude_with_image:
        "¿Que dialog es este? ¿Que boton debo clickear para cerrarlo SIN
         romper el sistema? Responde JSON: {action, x_relative, y_relative}"
  4. Ejecuta el click con pyautogui en las coords devueltas
  5. Loguea el incidente en data/dialog_incidents.jsonl
  6. Si el dialog REAPARECE 3+ veces, escala: pide a Claude un FIX PERMANENTE
     (ej: desinstalar app problematica, desactivar servicio, etc)

Asi Jarvis maneja popups sin intervencion humana.
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
INCIDENTS = DATA / "dialog_incidents.jsonl"
SCREENSHOTS = DATA / "dialog_screenshots"

TICK_SECONDS = 20  # cada 20 seg revisa pantalla

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[dialog_guardian {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def emit_incident(event: dict):
    INCIDENTS.parent.mkdir(parents=True, exist_ok=True)
    with INCIDENTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({**event, "ts": datetime.now().isoformat()},
                           ensure_ascii=False, default=str) + "\n")


def take_screenshot() -> Path | None:
    try:
        import pyautogui
        SCREENSHOTS.mkdir(parents=True, exist_ok=True)
        path = SCREENSHOTS / f"shot_{int(time.time())}.png"
        pyautogui.screenshot(str(path))
        return path
    except Exception as e:
        log(f"  screenshot fallo: {e}")
        return None


def detect_dialog_heuristic(screenshot_path: Path) -> dict | None:
    """Heuristica simple: usa OCR + Claude vision para detectar dialogs.

    Retorna dict con info del dialog o None si no detecta.
    """
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json, ping_proxy
    except ImportError:
        return None
    if not ping_proxy():
        return None

    # Preguntar a Claude vision si hay dialog
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_with_image
    except ImportError:
        return None

    prompt = (
        "Analiza esta screenshot de Windows. ¿Hay un DIALOG MODAL visible "
        "(error, popup, confirmacion, advertencia)? Si SI, responde JSON estricto:\n"
        '{"has_dialog": true, "dialog_type": "error|confirm|warning|info", '
        '"title": "titulo del dialog", "best_button": "texto del boton seguro a clickear", '
        '"button_x_pct": 0-100, "button_y_pct": 0-100, '
        '"recommended_fix": "descripcion de fix permanente si el dialog se repite"}\n\n'
        'Si NO hay dialog: {"has_dialog": false}\n'
        "IMPORTANTE: button_x_pct y button_y_pct son porcentajes (0-100) de la pantalla, "
        "no pixeles. El boton mas seguro suele ser 'Aceptar' o 'OK' o 'Cerrar', "
        "NO 'Reportar' ni 'Enviar info', NO 'Reiniciar', NO 'Apagar'."
    )

    try:
        # Necesito ask_claude_with_image que devuelva texto + parsear JSON
        text = ask_claude_with_image(prompt, str(screenshot_path), max_tokens=800)
        if not text:
            return None
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            if data.get("has_dialog"):
                return data
    except Exception as e:
        log(f"  Claude vision fallo: {e}")
    return None


def click_button(x_pct: float, y_pct: float):
    """Click en porcentaje de pantalla."""
    try:
        import pyautogui
        w, h = pyautogui.size()
        x = int(w * x_pct / 100)
        y = int(h * y_pct / 100)
        log(f"  clickeando en ({x}, {y}) [pantalla {w}x{h}]")
        pyautogui.moveTo(x, y, duration=0.5)
        time.sleep(0.3)
        pyautogui.click()
        return True
    except Exception as e:
        log(f"  click fallo: {e}")
        return False


def count_recent_incidents(dialog_title: str, hours: int = 1) -> int:
    """Cuenta incidentes del mismo dialog en las ultimas N horas."""
    if not INCIDENTS.exists():
        return 0
    from datetime import timedelta
    threshold = datetime.now() - timedelta(hours=hours)
    count = 0
    try:
        for line in INCIDENTS.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e.get("ts", ""))
                if ts > threshold and dialog_title.lower() in (e.get("title", "") or "").lower():
                    count += 1
            except Exception:
                continue
    except Exception:
        pass
    return count


def escalate_to_permanent_fix(dialog_info: dict):
    """Si el dialog se repite mucho, pedir a Claude un fix permanente."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
    except ImportError:
        return None

    prompt = (
        f"El dialog '{dialog_info.get('title')}' se ha repetido 3+ veces en la ultima hora.\n"
        f"Tipo: {dialog_info.get('dialog_type')}\n"
        f"Fix sugerido inicialmente: {dialog_info.get('recommended_fix')}\n\n"
        f"Eres ingeniero senior. Dame un FIX PERMANENTE (comando Windows o cambio "
        f"de configuracion) para que ese dialog NO vuelva a aparecer. Si el dialog viene "
        f"de una app rota (ej PowerToys.Awake crash), considera desactivar/desinstalar esa "
        f"app especifica. Si viene del SO, considera deshabilitar un servicio o tweak de "
        f"registro. Responde con el comando exacto en CMD o PowerShell."
    )
    answer = ask_claude(prompt, max_tokens=500)
    log(f"  ESCALATION fix: {(answer or '')[:200]}")
    emit_incident({
        "type": "ESCALATION",
        "dialog": dialog_info,
        "proposed_fix": answer,
    })
    return answer


def main():
    log(f"vigia dialogs iniciado (tick {TICK_SECONDS}s)")
    while True:
        try:
            shot = take_screenshot()
            if shot:
                dialog = detect_dialog_heuristic(shot)
                if dialog:
                    log(f"DIALOG: '{dialog.get('title')}' ({dialog.get('dialog_type')})")
                    log(f"  fix: clickear '{dialog.get('best_button')}' en ({dialog.get('button_x_pct')}%, {dialog.get('button_y_pct')}%)")
                    clicked = click_button(
                        dialog.get("button_x_pct", 50),
                        dialog.get("button_y_pct", 80),
                    )
                    emit_incident({
                        "title": dialog.get("title"),
                        "type": dialog.get("dialog_type"),
                        "button_clicked": dialog.get("best_button"),
                        "clicked_success": clicked,
                        "screenshot": str(shot),
                    })
                    # Escalation si se repite
                    recent = count_recent_incidents(dialog.get("title", ""), hours=1)
                    if recent >= 3:
                        log(f"  ALERT: '{dialog.get('title')}' x{recent} en 1h, escalando...")
                        escalate_to_permanent_fix(dialog)
                # Limpiar screenshots viejos (> 1 dia)
                cutoff = time.time() - 86400
                for f in SCREENSHOTS.glob("shot_*.png"):
                    if f.stat().st_mtime < cutoff:
                        try: f.unlink()
                        except Exception: pass
        except Exception as e:
            log(f"ERR tick: {e}")
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    main()
