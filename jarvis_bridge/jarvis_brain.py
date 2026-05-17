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
import os
import sys
import time
from pathlib import Path

import requests

PROXY = "http://127.0.0.1:8088"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT = 300  # subido de 120 -> 300 (proxy Max plan a veces tarda)

# Provider routing (FREE tier solamente, sin Anthropic paid API):
#   anthropic_proxy   (default) - via claude_proxy v1 :8088 OAuth Max
#   gemini_api        - Google Gemini API free tier (60 req/min flash)
#   gemini_browser    - browser bridge gemini_pro_server :5555 (needs NAT)
#   ollama            - 100% local en :11434 (sin internet, infinito)
LLM_PROVIDER = os.environ.get("JARVIS_LLM_PROVIDER", "anthropic_proxy").lower()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BROWSER_URL = os.environ.get("GEMINI_BROWSER_URL",
                                      "http://10.0.2.2:5555")
GEMINI_MODEL_DEFAULT = "gemini-2.5-flash"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL_DEFAULT = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")

# Fallback chain: si provider principal falla, prueba estos en orden.
# Default: anthropic_proxy → gemini_api → gemini_browser → ollama (local infinito)
# Ej env: JARVIS_LLM_FALLBACK="gemini_api,ollama"
_default_fallback = ("gemini_api,gemini_browser,ollama"
                      if LLM_PROVIDER == "anthropic_proxy" else "")
LLM_FALLBACK = [p.strip() for p in
                os.environ.get("JARVIS_LLM_FALLBACK", _default_fallback).split(",")
                if p.strip()]


def _proxy_healthy(timeout: float = 3.0) -> bool:
    """Quick health check ANTES de gastar tiempo en intentos largos."""
    try:
        r = requests.get(f"{PROXY}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def _ask_gemini_api(prompt: str, system: str, max_tokens: int,
                     timeout: int) -> str | None:
    """Llama Gemini via Google AI Studio free tier. Free 60 req/min Flash."""
    if not GEMINI_API_KEY:
        print("[jarvis_brain] GEMINI_API_KEY no seteado", file=sys.stderr)
        return None
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL_DEFAULT}:generateContent?key={GEMINI_API_KEY}")
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"maxOutputTokens": max_tokens,
                              "temperature": 0.7},
    }
    r = requests.post(url, json=body, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _ask_ollama(prompt: str, system: str, max_tokens: int,
                 timeout: int) -> str | None:
    """Ollama 100% local. Sin API key, sin internet. Modelo en OLLAMA_MODEL."""
    body = {
        "model": OLLAMA_MODEL_DEFAULT,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.7},
    }
    r = requests.post(f"{OLLAMA_URL}/api/generate", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json().get("response", "").strip() or None


def _ask_gemini_browser(prompt: str, system: str, timeout: int) -> str | None:
    """Llama gemini_pro_server (browser bridge) en :5555 - free Pro plan."""
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    try:
        r = requests.post(f"{GEMINI_BROWSER_URL}/ask",
                          json={"prompt": full_prompt},
                          timeout=timeout)
        r.raise_for_status()
        return r.json().get("response", "")
    except Exception as e:
        print(f"[jarvis_brain] gemini browser fail: {e}", file=sys.stderr)
        return None


def _try_provider(provider: str, prompt: str, system: str, model: str,
                   max_tokens: int, timeout: int, retries: int) -> str | None:
    """Llama un provider especifico. Devuelve texto o None si falla."""
    if provider == "gemini_api":
        for attempt in range(retries + 1):
            try:
                return _ask_gemini_api(prompt, system, max_tokens, timeout)
            except Exception as e:
                if attempt < retries:
                    time.sleep(min(30, 5 * (2 ** attempt)))
                    continue
                print(f"[brain] gemini_api fallo: {e}", file=sys.stderr)
        return None

    if provider == "gemini_browser":
        for attempt in range(retries + 1):
            try:
                r = _ask_gemini_browser(prompt, system, timeout)
                if r:
                    return r
            except Exception as e:
                if attempt < retries:
                    time.sleep(min(30, 5 * (2 ** attempt)))
                    continue
                print(f"[brain] gemini_browser fallo: {e}", file=sys.stderr)
        return None

    if provider == "ollama":
        for attempt in range(retries + 1):
            try:
                r = _ask_ollama(prompt, system, max_tokens, timeout)
                if r:
                    return r
            except Exception as e:
                if attempt < retries:
                    time.sleep(min(30, 5 * (2 ** attempt)))
                    continue
                print(f"[brain] ollama fallo: {e}", file=sys.stderr)
        return None

    if provider != "anthropic_proxy":
        print(f"[brain] unknown provider '{provider}' — skipping",
              file=sys.stderr)
        return None

    # anthropic_proxy
    if not _proxy_healthy(timeout=3.0):
        print(f"[brain] proxy DOWN", file=sys.stderr)
        return None
    payload = {"model": model, "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens}
    for attempt in range(retries + 1):
        try:
            r = requests.post(f"{PROXY}/v1/messages", json=payload,
                               timeout=timeout)
            r.raise_for_status()
            return r.json()["content"][0]["text"]
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt < retries:
                time.sleep(min(30, 5 * (2 ** attempt)))
                continue
            print(f"[brain] proxy timeout: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[brain] proxy error: {e}", file=sys.stderr)
            break
    return None


def ask_claude(
    prompt: str,
    system: str = "Eres Jarvis, asistente autonomo de Emmanuel. Respondes directo, sin preamble, en espanol.",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 3,
) -> str | None:
    """Pregunta al LLM con FALLBACK CHAIN automatico.

    Flow:
      1. Intenta provider primario (JARVIS_LLM_PROVIDER)
      2. Si None, prueba cada provider en LLM_FALLBACK
      3. Returns first successful

    Todos los providers free tier - NO API paga.
    """
    chain = [LLM_PROVIDER] + [p for p in LLM_FALLBACK if p != LLM_PROVIDER]
    for provider in chain:
        result = _try_provider(provider, prompt, system, model,
                                max_tokens, timeout, retries)
        if result:
            if provider != LLM_PROVIDER:
                print(f"[brain] OK via fallback '{provider}'", file=sys.stderr)
            return result
        print(f"[brain] provider '{provider}' fallo, probando siguiente",
              file=sys.stderr)
    print(f"[brain] ALL PROVIDERS FAILED ({chain})", file=sys.stderr)
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
