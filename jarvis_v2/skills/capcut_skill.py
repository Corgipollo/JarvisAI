"""capcut_skill.py - Jarvis aprende a usar CapCut Desktop.

Estrategia: vision LLM (Gemini/Claude) entiende la UI semantica, luego
desktop_hybrid + human_mouse ejecutan clicks fisicos.

Workflow tipico:
  1. open_capcut() - lanza app o trae foreground
  2. learn_ui() - screenshot + vision_analyze -> JSON de zonas (timeline,
     panel media, botones export, etc.) con coords aproximados
  3. import_media(path) - drag&drop o click "Import"
  4. add_clip_to_timeline()
  5. trim_clip(start_s, end_s)
  6. export(output_path)

Por ahora foco en open + learn_ui (lo basico para que Jarvis ENTIENDA CapCut).
Cada accion concreta (trim, export) requiere iteracion con templates.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CAPCUT_TEMPLATES = Path(r"C:/Jarvis/workspace/templates/capcut")
CAPCUT_TEMPLATES.mkdir(parents=True, exist_ok=True)
CAPCUT_LEARN_LOG = ROOT / "data" / "capcut_ui_knowledge.json"

CAPCUT_PATHS = [
    r"C:\Users\Emmanuel\AppData\Local\CapCut\Apps\CapCut.exe",
    r"C:\Program Files\CapCut\CapCut.exe",
    r"C:\Program Files (x86)\CapCut\CapCut.exe",
]


def open_capcut() -> dict:
    """Abre o foreground a CapCut."""
    try:
        import pygetwindow as gw
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                         "pygetwindow"])
        import pygetwindow as gw

    wins = gw.getWindowsWithTitle("CapCut")
    if wins:
        try:
            w = wins[0]
            if w.isMinimized:
                w.restore()
            w.activate()
            time.sleep(2)
            return {"ok": True, "method": "foreground_existing",
                    "title": w.title}
        except Exception as e:
            print(f"[capcut] activate fail: {e}", file=sys.stderr)

    for p in CAPCUT_PATHS:
        if Path(p).exists():
            subprocess.Popen([p])
            time.sleep(12)  # CapCut tarda en cargar
            return {"ok": True, "method": "launched", "exe": p}

    return {"ok": False, "error": "capcut_not_installed",
            "paths_tried": CAPCUT_PATHS,
            "hint": "Install via: winget install --id Bytedance.CapCut"}


def learn_ui(prompt_extra: str = "") -> dict:
    """Captura pantalla CapCut + Gemini analiza UI. Guarda conocimiento JSON."""
    from jarvis_v2.skills.vision_analyze import analyze_screenshot
    prompt = (
        "Estas viendo la app CapCut (editor de video). "
        "Lista TODAS las zonas y botones interactivos que ves con su funcion. "
        "Para cada uno indica: nombre del boton/zona, ubicacion aproximada en "
        "pantalla (esquina superior izquierda / centro / barra inferior / etc.), "
        "y proposito (importar media, trim, exportar, agregar efecto, etc.). "
        "Si ves el timeline, descibe la track activa y clips visibles. "
        "Devuelve formato JSON: {ui_zones: [{name, location, purpose, "
        "approximate_coords:[x,y]}]}. " + prompt_extra
    )
    r = analyze_screenshot(prompt, prefer="gemini")
    if not r.get("ok"):
        return r

    # Guardar conocimiento acumulado
    knowledge = []
    if CAPCUT_LEARN_LOG.exists():
        try:
            knowledge = json.loads(CAPCUT_LEARN_LOG.read_text(encoding="utf-8"))
        except Exception:
            knowledge = []
    knowledge.append({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "screenshot": r.get("screenshot_path"),
        "analysis": r["text"],
        "provider": r.get("provider"),
    })
    knowledge = knowledge[-50:]  # ultimas 50 lecciones
    CAPCUT_LEARN_LOG.write_text(json.dumps(knowledge, ensure_ascii=False,
                                             indent=2, default=str),
                                  encoding="utf-8")
    return r


def click_by_text(text: str) -> dict:
    """Click via OCR (desktop_hybrid) en CapCut."""
    from jarvis_v2.skills.desktop_hybrid import click_text
    return click_text(text)


def click_by_template(template_filename: str) -> dict:
    """Click via cv2.matchTemplate con template PNG en workspace/templates/capcut/."""
    from jarvis_v2.skills.desktop_hybrid import click_icon
    tpl_path = CAPCUT_TEMPLATES / template_filename
    if not tpl_path.exists():
        return {"ok": False, "error": f"template_not_found: {tpl_path}",
                "hint": f"Guarda PNG del icono en {CAPCUT_TEMPLATES}"}
    return click_icon(str(tpl_path), threshold=0.82)


def quick_export(output_name: str = "jarvis_export.mp4") -> dict:
    """Heuristic export: Ctrl+E (atajo) o click 'Export' via OCR."""
    import pyautogui
    pyautogui.hotkey("ctrl", "e")
    time.sleep(3)
    return {"ok": True, "method": "ctrl_e_shortcut",
            "next": "validar dialog Export y aceptar via click_by_text('Export')"}


if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else "open"
    if op == "open":
        print(json.dumps(open_capcut(), ensure_ascii=False, indent=2))
    elif op == "learn":
        extra = " ".join(sys.argv[2:])
        print(json.dumps(learn_ui(extra), ensure_ascii=False, indent=2)[:1500])
    elif op == "click":
        if len(sys.argv) < 3:
            print("uso: capcut_skill.py click <texto>")
            sys.exit(1)
        print(json.dumps(click_by_text(sys.argv[2]), ensure_ascii=False, indent=2))
    elif op == "export":
        print(json.dumps(quick_export(), ensure_ascii=False, indent=2))
