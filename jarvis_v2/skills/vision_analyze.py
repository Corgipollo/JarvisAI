"""vision_analyze.py - LLM vision: entiende IMAGENES, no solo texto OCR.

Diferencia con desktop_hybrid:
  - desktop_hybrid: OCR local + cv2 template matching. Solo lee TEXTO visible.
  - vision_analyze: pasa imagen a Gemini 2.0 Flash o Claude Haiku 4.5 (ambos
    soportan vision) para entender CONTENIDO semantico: que app es, que
    botones hay, que esta haciendo el usuario, que pasa en una foto, etc.

API:
    analyze_screenshot(prompt) -> str   (captura + analiza pantalla actual)
    analyze_image(img_path, prompt) -> str   (analiza imagen guardada)
    analyze_url_image(url, prompt) -> str    (analiza imagen de URL)

Provider auto: usa Gemini si GEMINI_API_KEY (free 1500/dia), sino OpenRouter
Haiku con vision (~$0.0015 por imagen).
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
WORKSPACE = ROOT / "workspace" / "vision"
WORKSPACE.mkdir(parents=True, exist_ok=True)


def _grab_screen_to_png(path: Path | None = None) -> Path:
    """Toma screenshot con mss y guarda PNG."""
    try:
        import mss
    except ImportError:
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", "mss"])
        import mss
    if path is None:
        path = WORKSPACE / f"shot_{int(time.time())}.png"
    with mss.mss() as sct:
        sct.shot(mon=1, output=str(path))
    return path


def _b64_image(img_path: Path) -> str:
    return base64.b64encode(img_path.read_bytes()).decode("ascii")


def analyze_with_gemini(img_path: Path, prompt: str) -> str | None:
    """Gemini 2.0 Flash con image (free 1500/dia)."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return None
    model = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-2.0-flash").replace("models/", "")
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    b64 = _b64_image(img_path)
    mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
    body = {
        "contents": [{"parts": [
            {"inline_data": {"mime_type": mime, "data": b64}},
            {"text": prompt},
        ]}],
        "generationConfig": {"maxOutputTokens": 2000, "temperature": 0.2},
    }
    try:
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        d = r.json()
        return d["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[vision] gemini fail: {e}", file=sys.stderr)
        return None


def analyze_with_openrouter(img_path: Path, prompt: str,
                              model: str = "anthropic/claude-haiku-4.5") -> str | None:
    """Claude Haiku vision via OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        return None
    b64 = _b64_image(img_path)
    mime = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Corgipollo/JarvisAI",
    }
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        "max_tokens": 2000,
        "temperature": 0.2,
    }
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                           headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[vision] openrouter fail: {e}", file=sys.stderr)
        return None


def analyze_image(img_path: str | Path, prompt: str,
                   prefer: str = "gemini") -> dict:
    """Analiza imagen con LLM vision. Devuelve {ok, text, provider}.

    prefer: 'gemini' (free) o 'openrouter' (~$0.0015).
    """
    img_path = Path(img_path)
    if not img_path.exists():
        return {"ok": False, "error": f"image_not_found: {img_path}"}

    if prefer == "gemini":
        text = analyze_with_gemini(img_path, prompt)
        if text:
            return {"ok": True, "text": text, "provider": "gemini-2.0-flash"}
        text = analyze_with_openrouter(img_path, prompt)
        if text:
            return {"ok": True, "text": text, "provider": "openrouter-haiku"}
    else:
        text = analyze_with_openrouter(img_path, prompt)
        if text:
            return {"ok": True, "text": text, "provider": "openrouter-haiku"}
        text = analyze_with_gemini(img_path, prompt)
        if text:
            return {"ok": True, "text": text, "provider": "gemini-2.0-flash"}

    return {"ok": False, "error": "both_providers_failed"}


def analyze_screenshot(prompt: str = "Describe lo que ves en esta pantalla. Si hay una aplicacion abierta, di cual. Lista botones y secciones visibles.",
                        prefer: str = "gemini") -> dict:
    """Captura pantalla actual + analiza con LLM vision."""
    img = _grab_screen_to_png()
    r = analyze_image(img, prompt, prefer=prefer)
    r["screenshot_path"] = str(img)
    return r


def analyze_url_image(url: str, prompt: str, prefer: str = "gemini") -> dict:
    """Descarga imagen de URL + analiza."""
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        suffix = ".png" if "png" in r.headers.get("content-type", "") else ".jpg"
        img = WORKSPACE / f"url_{int(time.time())}{suffix}"
        img.write_bytes(r.content)
    except Exception as e:
        return {"ok": False, "error": f"download_fail: {e}"}
    return analyze_image(img, prompt, prefer=prefer)


if __name__ == "__main__":
    import json
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "Que aplicacion esta abierta? Lista botones y zonas interactivas con su funcion."
    )
    r = analyze_screenshot(prompt)
    print(json.dumps(r, ensure_ascii=False, indent=2))
