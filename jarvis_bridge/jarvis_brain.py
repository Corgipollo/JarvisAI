"""jarvis_brain.py — Helper para que TODOS los scripts pregunten a Claude.

Wrapper sencillo del claude_proxy local. Cualquier script que necesite razonar
solo importa esto y llama ask_claude(prompt) -> str.

Costo: $0 (usa Claude CLI via OAuth Max plan).

Uso:
    from jarvis_bridge.jarvis_brain import ask_claude, ask_claude_with_image

    answer = ask_claude("¿Qué hago si el script falla con WinError 2?")
    decision = ask_claude_with_image("¿Qué hay en pantalla?", screenshot_path)
"""
from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import requests

PROXY = "http://127.0.0.1:8088"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT = 120


def ask_claude(
    prompt: str,
    system: str = "Eres Jarvis, asistente autonomo de Emmanuel. Respondes directo, sin preamble, en espanol.",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 2,
) -> str | None:
    """Pregunta a Claude via proxy local. Retorna texto o None si falla."""
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                f"{PROXY}/v1/messages",
                json={
                    "model": model,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                },
                timeout=timeout,
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            print(f"[jarvis_brain] fallo tras {retries+1} intentos: {e}", file=sys.stderr)
            return None


def ask_claude_with_image(
    prompt: str,
    image_path: str | Path,
    system: str = "Eres Jarvis. Describe lo que ves y razona sobre la accion siguiente.",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1500,
) -> str | None:
    """Pregunta a Claude con imagen adjunta (vision)."""
    image_path = Path(image_path)
    if not image_path.exists():
        return None
    try:
        img_b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
        ext = image_path.suffix.lower().lstrip(".")
        if ext == "jpg":
            ext = "jpeg"
        r = requests.post(
            f"{PROXY}/v1/messages",
            json={
                "model": model,
                "system": system,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": f"image/{ext}", "data": img_b64}},
                        {"type": "text", "text": prompt},
                    ],
                }],
                "max_tokens": max_tokens,
            },
            timeout=180,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]
    except Exception as e:
        print(f"[jarvis_brain] image ask fallo: {e}", file=sys.stderr)
        return None


def ask_claude_json(
    prompt: str,
    schema_hint: str = "JSON estricto: {key: value}",
    system: str | None = None,
    **kwargs,
) -> dict | None:
    """Pregunta a Claude esperando JSON valido."""
    sys_prompt = (
        system or
        f"Eres Jarvis. Respondes SOLO con JSON valido, sin markdown ni texto extra. {schema_hint}"
    )
    text = ask_claude(prompt, system=sys_prompt, **kwargs)
    if not text:
        return None
    # Extraer JSON si viene envuelto en ```json o texto
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def ping_proxy() -> bool:
    """Verifica que el proxy esta vivo."""
    try:
        r = requests.get(f"{PROXY}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


if __name__ == "__main__":
    if not ping_proxy():
        print("ERROR: proxy en :8088 no responde. Arranca claude_proxy.py primero.")
        sys.exit(1)

    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hola Jarvis, di que estas vivo."
    answer = ask_claude(q)
    print(answer or "(sin respuesta)")
