"""desktop_hybrid.py - Vision hibrida LOCAL para automatizar apps de escritorio.

Estrategia: NO mandar screenshots pesadas a la API. En su lugar:
  1. mss capture (RAM minima, ~50ms)
  2. pytesseract OCR -> texto + bounding boxes
  3. cv2.matchTemplate -> iconos guardados como PNG en workspace/templates/
  4. Devuelve JSON estructurado {texto_detectado: [{texto, coords}], iconos: [...]}
  5. Ese JSON se manda a Haiku via OpenRouter ($0.0001 por consulta vs $0.05
     si mandaramos screenshot a vision)
  6. Haiku elige texto/icono target -> coords -> human_mouse.human_click

Dependencias: mss, pytesseract, opencv-python, pillow.
Auto-install si faltan al primer uso.

API:
    scan_desktop(template_dir=None) -> dict
    find_text(needle: str) -> tuple[int,int] | None
    find_icon(template_path: str, threshold=0.85) -> tuple[int,int] | None
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_DIR = Path(r"C:/Jarvis/workspace/templates")
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

# Path tesseract.exe (instalado via START_JARVIS.bat winget UB-Mannheim.TesseractOCR)
_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _ensure_deps():
    """Auto-install si faltan libs (idempotente)."""
    needed = []
    try:
        import mss  # noqa
    except ImportError:
        needed.append("mss")
    try:
        import cv2  # noqa
    except ImportError:
        needed.append("opencv-python")
    try:
        import pytesseract  # noqa
    except ImportError:
        needed.append("pytesseract")
    try:
        import PIL  # noqa
    except ImportError:
        needed.append("pillow")
    if needed:
        print(f"[desktop_hybrid] installing missing: {needed}", file=sys.stderr)
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet",
                         *needed], check=False)


def _setup_tesseract():
    """Configura pytesseract.tesseract_cmd al binario."""
    import pytesseract
    for p in _TESSERACT_PATHS:
        if Path(p).exists():
            pytesseract.pytesseract.tesseract_cmd = p
            return p
    return None


def grab_screen(monitor: int = 1) -> "tuple":
    """mss capture del monitor (1=primario). Devuelve (PIL.Image, numpy array)."""
    _ensure_deps()
    import mss
    import numpy as np
    from PIL import Image
    with mss.mss() as sct:
        m = sct.monitors[monitor]
        raw = sct.grab(m)
        img_np = np.array(raw)  # BGRA
        img_pil = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
        return img_pil, img_np[:, :, :3]  # PIL RGB, numpy BGR


def ocr_text_with_coords(img_pil) -> list[dict]:
    """OCR via pytesseract con bounding boxes. Devuelve lista de
    {texto, coords:[cx,cy], box:[x,y,w,h], conf}."""
    _ensure_deps()
    _setup_tesseract()
    import pytesseract
    from pytesseract import Output

    data = pytesseract.image_to_data(img_pil, lang="eng+spa",
                                       output_type=Output.DICT,
                                       config="--oem 3 --psm 6")
    results = []
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        if not txt:
            continue
        try:
            conf = int(data["conf"][i])
        except (ValueError, KeyError):
            conf = 0
        if conf < 30:  # filtrar ruido
            continue
        x, y, w, h = (data["left"][i], data["top"][i],
                       data["width"][i], data["height"][i])
        cx, cy = x + w // 2, y + h // 2
        results.append({
            "texto": txt, "coords": [cx, cy],
            "box": [x, y, w, h], "conf": conf,
        })
    return results


def find_icons_in_screen(img_bgr_np, template_dir: Path = TEMPLATES_DIR,
                          threshold: float = 0.85) -> list[dict]:
    """cv2.matchTemplate contra todos los .png en template_dir.
    Devuelve [{name, coords, score, box}]."""
    _ensure_deps()
    import cv2
    import numpy as np

    if not template_dir.exists():
        return []
    icons = []
    for tpl_path in template_dir.glob("*.png"):
        try:
            tpl = cv2.imread(str(tpl_path), cv2.IMREAD_COLOR)
            if tpl is None:
                continue
            res = cv2.matchTemplate(img_bgr_np, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val >= threshold:
                h, w = tpl.shape[:2]
                cx, cy = max_loc[0] + w // 2, max_loc[1] + h // 2
                icons.append({
                    "name": tpl_path.stem,
                    "coords": [cx, cy],
                    "box": [max_loc[0], max_loc[1], w, h],
                    "score": round(float(max_val), 3),
                })
        except Exception as e:
            print(f"[desktop_hybrid] match fail {tpl_path.name}: {e}",
                  file=sys.stderr)
    return icons


def scan_desktop(template_dir: Path = TEMPLATES_DIR,
                  ocr_max_items: int = 80,
                  icon_threshold: float = 0.85) -> dict:
    """Escaneo completo del escritorio. Devuelve JSON listo para Haiku."""
    img_pil, img_bgr = grab_screen()
    texts = ocr_text_with_coords(img_pil)
    # Filtra por confianza y deja top N por tamaño (cosas pequeñas suelen ser ruido)
    texts_sorted = sorted(texts, key=lambda t: t["conf"], reverse=True)
    texts_top = texts_sorted[:ocr_max_items]

    icons = find_icons_in_screen(img_bgr, template_dir, icon_threshold)
    return {
        "screen_size": img_pil.size,
        "texto_detectado": texts_top,
        "iconos_detectados": icons,
    }


def find_text(needle: str, case_sensitive: bool = False) -> tuple[int, int] | None:
    """Busca texto en pantalla. Devuelve coords del primer match o None."""
    scan = scan_desktop()
    n = needle if case_sensitive else needle.lower()
    for item in scan["texto_detectado"]:
        t = item["texto"] if case_sensitive else item["texto"].lower()
        if n in t:
            return tuple(item["coords"])
    return None


def find_icon(template_path: str, threshold: float = 0.85) -> tuple[int, int] | None:
    """Busca un icono especifico (path absoluto a .png). Devuelve coords o None."""
    import cv2
    _, img_bgr = grab_screen()
    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None:
        return None
    res = cv2.matchTemplate(img_bgr, tpl, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val < threshold:
        return None
    h, w = tpl.shape[:2]
    return (max_loc[0] + w // 2, max_loc[1] + h // 2)


def click_text(needle: str) -> dict:
    """Busca texto en pantalla y hace click humano (Bezier)."""
    coords = find_text(needle)
    if not coords:
        return {"ok": False, "error": f"text_not_found: {needle}"}
    try:
        from jarvis_v2.swarm.human_mouse import human_click
        human_click(coords[0], coords[1])
        return {"ok": True, "coords": coords, "target": needle}
    except Exception as e:
        return {"ok": False, "error": f"click_fail: {e}"}


def click_icon(template_path: str, threshold: float = 0.85) -> dict:
    """Busca icono y hace click humano."""
    coords = find_icon(template_path, threshold)
    if not coords:
        return {"ok": False, "error": f"icon_not_found: {template_path}"}
    try:
        from jarvis_v2.swarm.human_mouse import human_click
        human_click(coords[0], coords[1])
        return {"ok": True, "coords": coords, "template": template_path}
    except Exception as e:
        return {"ok": False, "error": f"click_fail: {e}"}


if __name__ == "__main__":
    print("=== desktop_hybrid smoke test ===")
    _ensure_deps()
    tess = _setup_tesseract()
    print(f"tesseract: {tess}")
    print(f"templates dir: {TEMPLATES_DIR} ({len(list(TEMPLATES_DIR.glob('*.png')))} pngs)")
    scan = scan_desktop()
    print(f"screen: {scan['screen_size']}")
    print(f"OCR detectados: {len(scan['texto_detectado'])}")
    if scan["texto_detectado"]:
        print("  sample (top 5):")
        for t in scan["texto_detectado"][:5]:
            print(f"    '{t['texto'][:40]}' @ {t['coords']} conf={t['conf']}")
    print(f"iconos detectados: {len(scan['iconos_detectados'])}")
    out = ROOT / "data" / "desktop_scan.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"full scan saved to {out}")
