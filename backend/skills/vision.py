"""vision.py — Screenshot + OCR para que Jarvis SEPA que hay en pantalla.

Cascada OCR:
  1. Tesseract via pytesseract (si esta instalado en el sistema)
  2. Gemini Vision via gemini_pro_server localhost:5555 (cuando este vivo)
  3. EasyOCR si esta instalado
  4. Stub: "no OCR available"

Screenshot: pyautogui (basico) + opcional region.
"""
from __future__ import annotations

import base64
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "screenshots"

try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import pytesseract
    from PIL import Image
    # Default path Windows install via winget
    _tess_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for _p in _tess_paths:
        from pathlib import Path as _P
        if _P(_p).exists():
            pytesseract.pytesseract.tesseract_cmd = _p
            break
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def screenshot(region: Optional[tuple] = None, save: bool = True) -> dict:
    """Toma screenshot de la pantalla completa o region (x, y, w, h).

    Si save=True, guarda PNG y devuelve path. Si False, devuelve base64.
    """
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no disponible"}
    try:
        img = pyautogui.screenshot(region=region) if region else pyautogui.screenshot()
        if save:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:18]
            out = DATA_DIR / f"screen_{ts}.png"
            img.save(out)
            return {"success": True, "path": str(out), "size": img.size}
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        return {"success": True, "base64": b64, "size": img.size}
    except Exception as e:
        return {"success": False, "error": str(e)}


def ocr_tesseract(image_path: str, lang: str = "spa+eng") -> dict:
    if not HAS_TESSERACT:
        return {"success": False, "error": "pytesseract no instalado"}
    try:
        text = pytesseract.image_to_string(Image.open(image_path), lang=lang)
        return {"success": True, "text": text.strip(), "engine": "tesseract"}
    except Exception as e:
        return {"success": False, "error": str(e), "engine": "tesseract"}


def ocr_gemini_server(image_path: str, prompt: str = "Lee TODO el texto de la pantalla. Devuelve solo el texto, sin explicaciones.") -> dict:
    """Usa gemini_pro_server con la imagen via base64."""
    if not HAS_REQUESTS:
        return {"success": False, "error": "requests no instalado"}
    server = os.getenv("GEMINI_SERVER_URL", "http://localhost:5555")
    try:
        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        r = requests.post(
            f"{server}/ask",
            json={"prompt": prompt, "image_base64": b64, "reset": True},
            timeout=120,
        )
        r.raise_for_status()
        return {"success": True, "text": r.json().get("response", ""), "engine": "gemini_vision"}
    except Exception as e:
        return {"success": False, "error": str(e), "engine": "gemini_vision"}


def read_screen(region: Optional[tuple] = None, prompt: Optional[str] = None) -> dict:
    """Pipeline completo: screenshot + OCR cascada (tesseract -> gemini)."""
    sc = screenshot(region=region, save=True)
    if not sc["success"]:
        return sc
    path = sc["path"]

    # Cascada OCR
    if HAS_TESSERACT:
        r = ocr_tesseract(path)
        if r["success"] and len(r["text"]) > 2:
            r["screenshot_path"] = path
            return r

    # Fallback Gemini
    use_prompt = prompt or "Lee TODO el texto visible de la pantalla. Devuelve solo el texto."
    r = ocr_gemini_server(path, use_prompt)
    r["screenshot_path"] = path
    return r


def find_text_position(text_to_find: str, region: Optional[tuple] = None) -> dict:
    """Busca un texto en la pantalla y devuelve coordenadas aproximadas.

    Solo funciona con tesseract (necesita boxes). Devuelve None si no encuentra.
    """
    if not HAS_TESSERACT:
        return {"success": False, "error": "tesseract requerido para find_text_position"}
    sc = screenshot(region=region, save=True)
    if not sc["success"]:
        return sc
    try:
        data = pytesseract.image_to_data(
            Image.open(sc["path"]),
            lang="spa+eng",
            output_type=pytesseract.Output.DICT,
        )
        for i, word in enumerate(data["text"]):
            if text_to_find.lower() in word.lower():
                x = data["left"][i] + data["width"][i] // 2
                y = data["top"][i] + data["height"][i] // 2
                if region:
                    x += region[0]
                    y += region[1]
                return {"success": True, "x": x, "y": y, "matched": word}
        return {"success": False, "error": f"no encontre '{text_to_find}' en pantalla"}
    except Exception as e:
        return {"success": False, "error": str(e)}
