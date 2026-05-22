"""vision_locate.py - Visión semántica: locate-by-description universal.

Reemplaza OCR ciego con LLM vision para encontrar elementos visuales por
criterio semántico (no solo texto). Ejemplos:
  - "el BotFather verificado con check azul" (vs clones)
  - "el botón Export en CapCut (esquina superior derecha)"
  - "el icono de Telegram en la barra de tareas"
  - "el primer tweet del feed con más de 100 likes"
  - "el botón de descargar PDF en esta página"

Bidirectional with desktop_hybrid:
  - desktop_hybrid: OCR + cv2 templates (rápido, local, $0)
  - vision_locate: LLM vision (semántica, ~$0.001/call con Haiku via OAuth proxy)

Estrategia óptima:
  Si la descripción tiene texto exacto -> intentar desktop_hybrid.find_text primero.
  Si requiere criterio visual (color, icono, posición relativa) -> vision_locate.

API:
  locate(description, region=None) -> (x, y) | None
  locate_and_click(description) -> dict
  locate_multiple(description, count=3) -> list[(x, y)]
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _build_prompt(description: str, expected_count: int = 1) -> str:
    """Construye prompt para LLM vision con instrucciones precisas."""
    base = (
        "Estás viendo una captura de pantalla de Windows. Tu trabajo: localizar "
        "elementos visuales con CRITERIO SEMÁNTICO (no solo texto plano).\n\n"
        f"OBJETIVO: {description}\n\n"
        "REGLAS:\n"
        "1. Si encuentras el elemento exacto, devuelve sus coordenadas pixel "
        "del CENTRO en pantalla (eje X horizontal 0=izquierda, eje Y vertical "
        "0=arriba).\n"
        "2. Si hay varios candidatos, elige el que MEJOR cumple el criterio "
        "semántico, no el primero alfabético.\n"
        "3. Si NO encuentras nada que cumpla el criterio, devuelve x=0, y=0, "
        "found=false.\n"
        "4. Responde EXACTAMENTE en formato JSON sin texto adicional:\n"
    )
    if expected_count == 1:
        base += (
            '{"x": <int>, "y": <int>, "found": true|false, '
            '"reason": "<por qué este es el correcto>"}'
        )
    else:
        base += (
            f'{{"matches": [{{"x": <int>, "y": <int>, "rank": 1, "reason": "..."}}, '
            f'... hasta {expected_count} elementos], "found": true|false}}'
        )
    return base


def _capture_and_analyze(prompt: str,
                          screenshot_path: Path | None = None) -> dict:
    """Toma screenshot + manda a vision LLM. Devuelve dict parseado."""
    from jarvis_v2.skills.vision_analyze import analyze_screenshot, analyze_image
    if screenshot_path:
        r = analyze_image(screenshot_path, prompt, prefer="gemini")
    else:
        r = analyze_screenshot(prompt, prefer="gemini")
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "vision_fail")}

    text = r.get("text", "")
    # Strip markdown code fences si los hay
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```\s*$", "", text)

    # Find primer JSON object
    m = re.search(r"\{[\s\S]*?\}", text)
    if not m:
        return {"ok": False, "error": "no_json_in_response",
                "raw_head": text[:300]}
    try:
        parsed = json.loads(m.group(0))
        parsed["ok"] = True
        parsed["provider"] = r.get("provider", "?")
        return parsed
    except json.JSONDecodeError as e:
        # Cleanup trailing commas
        cleaned = re.sub(r",\s*([\]}])", r"\1", m.group(0))
        try:
            parsed = json.loads(cleaned)
            parsed["ok"] = True
            parsed["provider"] = r.get("provider", "?")
            return parsed
        except json.JSONDecodeError:
            return {"ok": False, "error": f"json_decode: {e}",
                    "raw_head": text[:300]}


def locate(description: str,
            screenshot_path: Path | None = None,
            min_x: int = 0, min_y: int = 0,
            max_x: int = 99999, max_y: int = 99999) -> tuple[int, int] | None:
    """Devuelve (x, y) del centro del elemento descrito. None si no se halla.

    min/max permite restringir a una región (ej: solo barra superior del navegador).
    """
    prompt = _build_prompt(description, expected_count=1)
    r = _capture_and_analyze(prompt, screenshot_path)
    if not r.get("ok"):
        print(f"[vision_locate] fail: {r.get('error')}", file=sys.stderr)
        return None
    if not r.get("found", False):
        print(f"[vision_locate] not found: {r.get('reason', '')}",
              file=sys.stderr)
        return None
    try:
        x, y = int(r["x"]), int(r["y"])
    except (KeyError, ValueError, TypeError):
        return None
    if x <= 0 and y <= 0:
        return None
    if not (min_x <= x <= max_x and min_y <= y <= max_y):
        print(f"[vision_locate] coords ({x},{y}) fuera de region requested",
              file=sys.stderr)
        return None
    print(f"[vision_locate] @ ({x},{y}) - {r.get('reason', '')[:80]} "
          f"[{r.get('provider')}]", file=sys.stderr)
    return (x, y)


def locate_multiple(description: str,
                     count: int = 3,
                     screenshot_path: Path | None = None) -> list[tuple[int, int]]:
    """Devuelve hasta N matches rankeados por relevancia."""
    prompt = _build_prompt(description, expected_count=count)
    r = _capture_and_analyze(prompt, screenshot_path)
    if not r.get("ok") or not r.get("found", False):
        return []
    matches = r.get("matches", [])
    out = []
    for m in matches[:count]:
        try:
            out.append((int(m["x"]), int(m["y"])))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def locate_and_click(description: str,
                      double_click: bool = False,
                      verify_after: bool = False) -> dict:
    """Localiza + click humano (Bezier). Si verify_after, screenshot post-click
    para confirmar que cambió la pantalla."""
    coords = locate(description)
    if not coords:
        return {"ok": False, "error": "not_found", "description": description}
    x, y = coords
    try:
        from jarvis_v2.swarm.human_mouse import human_click
        if double_click:
            human_click(x, y)
            time.sleep(0.15)
            human_click(x, y)
        else:
            human_click(x, y)
        result = {"ok": True, "coords": [x, y], "description": description}
        if verify_after:
            time.sleep(1.2)
            from jarvis_v2.skills.vision_analyze import analyze_screenshot
            v = analyze_screenshot(
                f"Acabo de hacer click esperando: '{description}'. "
                f"¿La pantalla cambió como se esperaba? "
                f'Responde JSON {{"changed": true|false, "now_visible": "..."}}',
                prefer="gemini",
            )
            result["verify"] = v.get("text", "")[:200]
        return result
    except Exception as e:
        return {"ok": False, "error": f"click_fail: {e}", "coords": [x, y]}


def smart_locate(description: str, fallback_text: str | None = None) -> tuple[int, int] | None:
    """Estrategia óptima:
       1. Si fallback_text proporcionado, intenta OCR rápido primero ($0)
       2. Si no hit o no proporcionado, va a vision LLM (~$0.001)
    Útil para tareas donde el texto exacto es conocido pero hay clones
    (entonces OCR puede dar coords falsas y vision desambigua)."""
    if fallback_text:
        try:
            from jarvis_v2.skills.desktop_hybrid import find_text
            r = find_text(fallback_text, case_sensitive=False)
            if r:
                # OCR encontró algo. Pero si la descripción semántica tiene
                # "verificado", "oficial", "primer", "real" -> mejor vision
                if any(kw in description.lower() for kw in
                        ("verificado", "verified", "oficial", "official",
                         "real", "auténtico", "primer", "first", "azul",
                         "con check", "con badge")):
                    pass  # cae a vision_locate abajo
                else:
                    return r
        except Exception:
            pass
    return locate(description)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("uso: vision_locate.py 'descripcion del elemento'")
        sys.exit(1)
    desc = " ".join(sys.argv[1:])
    coords = locate(desc)
    print(json.dumps({"description": desc, "coords": coords},
                      ensure_ascii=False))
