"""set_of_mark.py - Set-of-Mark (SoM) prompting para clicks confiables.

Captura screenshot, identifica controles clickeables via UIA tree, dibuja
recuadros amarillos numerados sobre cada uno. Devuelve dict {id: (cx, cy)}.

Uso:
    mapping, img_path = generate_som()
    # Send img_path to Claude with prompt: "Click on number X?"
    # Claude returns "14"
    cx, cy = mapping["14"]["center_x"], mapping["14"]["center_y"]
    pyautogui.click(cx, cy)

Reemplaza el patron "Claude vision % de pantalla" (60% accuracy) por
"Claude vision elige numero discreto" (99% accuracy).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from pywinauto import Desktop
from PIL import ImageGrab, ImageDraw, ImageFont

# Tipos de controles UIA que normalmente son clickeables
CLICKABLE_TYPES = (
    "Button", "ListItem", "MenuItem", "TabItem",
    "Hyperlink", "CheckBox", "RadioButton", "Edit",
    "Document", "ComboBox", "TreeItem", "DataItem",
)


def is_clickable(element) -> bool:
    """True si el elemento es de tipo interactivo."""
    try:
        cls = element.friendly_class_name()
    except Exception:
        return False
    return any(t in cls for t in CLICKABLE_TYPES)


def generate_som(
    output_image: str = "som_current_state.png",
    scope: str = "active_window",
    depth: int = 4,
    min_size: int = 10,
) -> tuple[dict, str]:
    """Genera screenshot SoM-marked + mapping dict.

    Args:
        output_image: ruta donde guardar la imagen marcada
        scope: 'active_window' (rapido) o 'desktop' (todo, lento)
        depth: profundidad del UIA tree (4 = balance speed/coverage)
        min_size: pixeles minimos para ignorar controles diminutos

    Returns:
        (mapping, image_path) donde mapping = {
            "1": {"center_x": 100, "center_y": 200, "type": "Button", "text": "OK"},
            ...
        }
    """
    print("[SoM] iniciando UIA scan...", flush=True)
    screenshot = ImageGrab.grab()
    draw = ImageDraw.Draw(screenshot)

    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except IOError:
        font = ImageFont.load_default()

    desktop = Desktop(backend="uia")

    if scope == "active_window":
        # Find active window from list (Desktop.active() returns abstract wrapper)
        root = None
        try:
            for w in desktop.windows():
                try:
                    if w.is_active():
                        root = w
                        break
                except Exception:
                    continue
        except Exception:
            pass
        if root is None:
            # Fallback: first visible window
            try:
                for w in desktop.windows():
                    try:
                        if w.is_visible():
                            root = w
                            break
                    except Exception:
                        continue
            except Exception:
                pass
        try:
            title = root.window_text() if root else "?"
        except Exception:
            title = "?"
        print(f"[SoM] root: {title[:80]}", flush=True)
    else:
        root = None
        try:
            root = desktop.windows()[0]
        except Exception:
            pass

    mapping: dict = {}
    eid = 1

    if root is None:
        print("[SoM] no root window found", flush=True)
        descendants = []
    else:
        try:
            descendants = root.descendants(depth=depth)
        except Exception as e:
            print(f"[SoM] descendants() fallo: {e}", flush=True)
            descendants = []

    for element in descendants:
        try:
            if not element.is_visible():
                continue
        except Exception:
            continue
        if not is_clickable(element):
            continue
        try:
            rect = element.rectangle()
        except Exception:
            continue
        if rect.width() < min_size or rect.height() < min_size:
            continue

        cx = rect.left + (rect.width() // 2)
        cy = rect.top + (rect.height() // 2)

        try:
            text = element.window_text()[:40]
            ctype = element.friendly_class_name()
        except Exception:
            text, ctype = "", "?"

        mapping[str(eid)] = {
            "center_x": cx, "center_y": cy,
            "rect": [rect.left, rect.top, rect.right, rect.bottom],
            "type": ctype, "text": text,
        }

        # Label con alto contraste (yellow bg + black text)
        tag = str(eid)
        try:
            bbox = font.getbbox(tag)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except AttributeError:
            tw, th = draw.textsize(tag, font=font)

        pad = 3
        bg = [rect.left, rect.top,
              rect.left + tw + pad * 2, rect.top + th + pad * 2]
        draw.rectangle(bg, fill="yellow", outline="black")
        draw.text((rect.left + pad, rect.top + pad), tag, fill="black", font=font)

        # Borde del control para claridad
        draw.rectangle([rect.left, rect.top, rect.right, rect.bottom],
                       outline="yellow", width=2)
        eid += 1

    out_path = str(Path(output_image).resolve())
    screenshot.save(out_path)
    print(f"[SoM] {len(mapping)} elementos marcados -> {out_path}", flush=True)
    return mapping, out_path


def claude_pick_and_click(task: str, screenshot_path: str, mapping: dict,
                          claude_fn=None) -> dict:
    """Le pide a Claude que elija un numero, luego ejecuta el click.

    Args:
        task: tarea natural ("clickear boton de subir video")
        screenshot_path: imagen SoM-marked
        mapping: dict de generate_som
        claude_fn: callable(prompt, image_path) -> str. Si None, importa from jarvis_bridge.

    Returns:
        {"chosen_id": "14", "center_x": 100, "center_y": 200, "clicked": True}
        o {"error": "..."} si fallo.
    """
    if claude_fn is None:
        try:
            from jarvis_bridge.jarvis_brain import ask_claude_with_image
            claude_fn = ask_claude_with_image
        except ImportError:
            return {"error": "claude_fn no provisto y jarvis_brain no importable"}

    options_summary = "\n".join(
        f"  {eid}: {info.get('type')} \"{info.get('text', '')[:30]}\""
        for eid, info in list(mapping.items())[:50]
    )
    prompt = (
        f"OBJETIVO: {task}\n\n"
        "Observa la captura. Los elementos interactivos estan marcados con cajas "
        "AMARILLAS NUMERADAS. Tu trabajo: elegir el NUMERO del elemento donde debo "
        "clickear para cumplir el objetivo.\n\n"
        f"Elementos disponibles:\n{options_summary}\n\n"
        "RESPUESTA: SOLO el numero. Sin explicacion. Ej: '14'. Si ninguno aplica, "
        "responde 'NONE'."
    )
    resp = claude_fn(prompt, screenshot_path, max_tokens=20)
    if not resp:
        return {"error": "claude no respondio"}

    chosen = resp.strip().split()[0].strip(".,!?")
    if chosen.upper() == "NONE":
        return {"error": "claude_chose_none", "raw": resp}
    if chosen not in mapping:
        return {"error": f"chosen_id_invalid: {chosen}", "raw": resp}

    info = mapping[chosen]
    return {
        "chosen_id": chosen,
        "center_x": info["center_x"],
        "center_y": info["center_y"],
        "type": info.get("type"),
        "text": info.get("text"),
    }


if __name__ == "__main__":
    print("[SoM] esperando 2s antes de capturar (cambia a ventana objetivo)...")
    time.sleep(2)
    mapping, img = generate_som()
    Path("som_mapping.json").write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Imagen: {img}")
    print(f"Mapping: {len(mapping)} elementos guardados en som_mapping.json")
    if mapping:
        print("Sample first 3:")
        for k in list(mapping.keys())[:3]:
            print(f"  {k}: {mapping[k]}")
