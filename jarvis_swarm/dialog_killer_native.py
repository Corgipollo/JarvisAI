"""dialog_killer_native.py — Cierra dialogs Windows via UI Automation NATIVA.

A diferencia de dialog_guardian (que usa Claude vision + click por pixel,
lento y poco fiable), este agente usa pywinauto que habla con la API de
Windows UI Automation directamente:

  1. Cada 5 seg enumera TODAS las ventanas Windows
  2. Filtra por title/classname tipico de dialogs (Error, Application Error,
     Microsoft Visual C++ Runtime, etc)
  3. Si encuentra dialog: busca el boton 'Aceptar'/'OK'/'Cerrar'/'Close'
  4. Hace click() nativo (no pixel)
  5. Loguea cada cierre

Sin Claude. Sin OCR. Solo Windows API. Velocidad: ~50ms por dialog.
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
LOG_FILE = DATA / "dialog_killer.log"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    line = f"[dialog_killer {datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# Titulos/patrones de dialogs que queremos cerrar automaticamente
DIALOG_PATTERNS = [
    "Error de la aplicación",
    "Application Error",
    "Microsoft Visual C++ Runtime",
    "Se produjo un error",
    "Se ha cerrado la sesión",
    "Se ha producido un problema",
    "Has dejado de funcionar",
    "Stopped working",
    "Crash",
    ".exe - Error",
    "Activar Windows",
    "Activar ahora",
    "Confirmar uso de PowerToys",
    "Reportar problema",
    "Send report",
]

# Botones aceptables para clickear (orden de preferencia: cerrar sin reportar)
BUTTON_PATTERNS = [
    "Cerrar el programa",
    "Cerrar",
    "Close",
    "No enviar",
    "Don't send",
    "Cancelar",
    "Cancel",
    "Aceptar",
    "OK",
    "Ok",
    "Ignorar",
    "Ignore",
    "Más tarde",
    "Skip",
]


def matches_dialog_pattern(title: str) -> bool:
    title_lower = title.lower()
    for p in DIALOG_PATTERNS:
        if p.lower() in title_lower:
            return True
    return False


def kill_dialog_pywinauto():
    """Usa pywinauto Desktop para enumerar ventanas y cerrar dialogs."""
    try:
        from pywinauto import Desktop
    except ImportError:
        log("pywinauto no instalado, pip install pywinauto")
        return 0

    killed = 0
    try:
        desktop = Desktop(backend="uia")
        for win in desktop.windows():
            try:
                title = win.window_text() or ""
                if not title:
                    continue
                if matches_dialog_pattern(title):
                    log(f"DIALOG detectado: '{title}'")
                    # Buscar boton para clickear
                    clicked = False
                    for btn_pattern in BUTTON_PATTERNS:
                        try:
                            btn = win.child_window(title=btn_pattern, control_type="Button")
                            if btn.exists(timeout=1):
                                btn.click()
                                log(f"  clicked '{btn_pattern}' OK")
                                killed += 1
                                clicked = True
                                break
                        except Exception:
                            continue
                    if not clicked:
                        # Fallback: cerrar ventana con close()
                        try:
                            win.close()
                            log(f"  fallback close() OK")
                            killed += 1
                        except Exception as e:
                            log(f"  fallback close fallo: {e}")
            except Exception as e:
                continue
    except Exception as e:
        log(f"  enumerar windows fallo: {e}")

    return killed


def main():
    log("dialog_killer NATIVO arrancado")
    # Auto-install pywinauto si no esta
    try:
        import pywinauto
    except ImportError:
        log("instalando pywinauto...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "pywinauto"],
                       capture_output=True)

    while True:
        try:
            n = kill_dialog_pywinauto()
            if n > 0:
                log(f"  cerrados {n} dialog(s) en este tick")
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"  tick fallo: {e}")
        time.sleep(5)


if __name__ == "__main__":
    main()
