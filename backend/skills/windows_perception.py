"""windows_perception.py — Percepcion DUAL del sistema para Jarvis.

Un humano ve la pantalla como PIXELES. Jarvis tiene 2 modos de percepcion:

  MODO HUMANO (visual):
    - screenshot + OCR (vision.py ya)
    - Lo que un humano ve

  MODO MAQUINA (estructural / bits):
    - UIA tree de Windows (cada control con propiedades)
    - Window handles (HWNDs)
    - Registry keys
    - Process info
    - Pixel colors exactos
    - Geometria de ventanas (coords, z-order)
    - Hijos/padres de cada elemento
    - Estado interno (enabled, focused, value, etc.)

Combinar ambas: humano ve "boton azul que dice OK", Jarvis ademas ve:
  - automation_id="confirmDialog_btnOK"
  - class="Button"
  - bounds=[840,560,920,590]
  - parent=Dialog#42
  - is_focused=True
  - keyboard_shortcut="Alt+O"

Eso es MUCHO mas informacion que un humano. Jarvis aprende patrones que
no se ven en pixels.

Uso:
    from backend.skills.windows_perception import perceive_active_window
    info = perceive_active_window()
    # info["uia_tree"], info["screenshot_b64"], info["registry_state"], ...
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False

try:
    from pywinauto import Desktop, Application
    HAS_PYWINAUTO = True
except ImportError:
    HAS_PYWINAUTO = False


def get_active_window() -> dict:
    """Info de la ventana activa (con focus)."""
    if not HAS_PYGETWINDOW:
        return {"error": "pygetwindow no instalado"}
    try:
        w = gw.getActiveWindow()
        if not w:
            return {"error": "no hay ventana activa"}
        return {
            "title": w.title,
            "bounds": [w.left, w.top, w.right, w.bottom],
            "size": [w.width, w.height],
            "is_maximized": w.isMaximized,
            "is_minimized": w.isMinimized,
        }
    except Exception as e:
        return {"error": str(e)}


def get_uia_tree(window_title: str | None = None, max_depth: int = 4) -> dict:
    """Devuelve el UIA tree (estructura interna) de una ventana.

    Cada nodo: {name, class, automation_id, control_type, bounds, value,
                is_enabled, is_focused, children: [...]}
    """
    if not HAS_PYWINAUTO:
        return {"error": "pywinauto no instalado: pip install pywinauto"}

    try:
        desktop = Desktop(backend="uia")
        if window_title:
            windows = [w for w in desktop.windows() if window_title.lower() in w.window_text().lower()]
        else:
            # Ventana con focus
            windows = [w for w in desktop.windows() if w.has_focus()]
        if not windows:
            return {"error": f"no encontre ventana '{window_title}'"}

        root = windows[0]

        def walk(elem, depth=0):
            if depth > max_depth:
                return None
            try:
                rect = elem.rectangle()
                node = {
                    "name": elem.window_text()[:80] if elem.window_text() else "",
                    "class": elem.class_name() or "",
                    "control_type": str(elem.element_info.control_type) if elem.element_info else "",
                    "automation_id": elem.element_info.automation_id if elem.element_info else "",
                    "bounds": [rect.left, rect.top, rect.right, rect.bottom],
                    "is_enabled": elem.is_enabled(),
                    "is_visible": elem.is_visible(),
                }
                # Children
                try:
                    children = elem.children()
                    if children and depth < max_depth:
                        node["children"] = [walk(c, depth+1) for c in children[:20]]
                        node["children"] = [c for c in node["children"] if c]
                except Exception:
                    pass
                return node
            except Exception:
                return None

        tree = walk(root)
        return {"window": root.window_text(), "tree": tree}
    except Exception as e:
        return {"error": str(e)}


def get_all_processes(limit: int = 30) -> list[dict]:
    """Top N procesos ordenados por RAM."""
    if not HAS_PSUTIL:
        return [{"error": "psutil no instalado"}]
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
            try:
                info = p.info
                procs.append({
                    "pid": info["pid"],
                    "name": info["name"],
                    "ram_mb": round(info["memory_info"].rss / 1e6, 1) if info["memory_info"] else 0,
                })
            except Exception:
                continue
        procs.sort(key=lambda p: p["ram_mb"], reverse=True)
        return procs[:limit]
    except Exception as e:
        return [{"error": str(e)}]


def read_pixel(x: int, y: int) -> dict:
    """Color RGB exacto en coordenada."""
    if not HAS_PYAUTOGUI:
        return {"error": "pyautogui no instalado"}
    try:
        rgb = pyautogui.pixel(x, y)
        return {"x": x, "y": y, "rgb": list(rgb), "hex": "#{:02x}{:02x}{:02x}".format(*rgb)}
    except Exception as e:
        return {"error": str(e)}


def get_all_windows() -> list[dict]:
    """Lista todas las ventanas abiertas con sus bounds."""
    if not HAS_PYGETWINDOW:
        return [{"error": "pygetwindow no instalado"}]
    try:
        result = []
        for w in gw.getAllWindows():
            if w.title and w.width > 0 and w.height > 0:
                result.append({
                    "title": w.title[:80],
                    "bounds": [w.left, w.top, w.right, w.bottom],
                    "size": [w.width, w.height],
                })
        return result
    except Exception as e:
        return [{"error": str(e)}]


def perceive_active_window(include_screenshot: bool = False,
                            include_uia: bool = True,
                            include_processes: bool = False) -> dict:
    """Percepcion completa de la ventana activa.

    Combina TODOS los modos de percepcion en un solo dict:
      - active_window: bounds + title
      - uia_tree: estructura interna (control_type, automation_id, etc.)
      - all_windows: lista de todas las ventanas (z-order)
      - screen_size: resolucion
      - active_processes: top 10 por RAM (opcional)
      - screenshot: PNG base64 (opcional, default off)
    """
    result = {
        "active_window": get_active_window(),
        "screen_size": pyautogui.size() if HAS_PYAUTOGUI else None,
        "all_windows": get_all_windows()[:20],
    }
    if HAS_PYAUTOGUI and result["screen_size"]:
        result["screen_size"] = {"w": result["screen_size"][0], "h": result["screen_size"][1]}

    if include_uia and HAS_PYWINAUTO:
        result["uia_tree"] = get_uia_tree(max_depth=3)

    if include_processes:
        result["top_processes"] = get_all_processes(limit=10)

    if include_screenshot and HAS_PYAUTOGUI:
        img = pyautogui.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result["screenshot_b64"] = base64.b64encode(buf.getvalue()).decode()[:200] + "..."

    return result


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    perception = perceive_active_window(include_processes=True)
    print(json.dumps(perception, ensure_ascii=False, indent=2, default=str)[:3000])
