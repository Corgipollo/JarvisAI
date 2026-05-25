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

PROXY = os.environ.get("JARVIS_CLAUDE_PROXY", "http://127.0.0.1:8088")
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_TIMEOUT = 300  # subido de 120 -> 300 (proxy Max plan a veces tarda)

# Provider routing:
#   openrouter        - HTTP API, dynamic router Haiku<->Sonnet (paid, indispensable)
#   anthropic_proxy   - claude_proxy v1 :8088 OAuth Max (FREE pero lento via CLI)
#   gemini_api        - Google Gemini API (free 1500/dia gemini-2.0-flash)
#   gemini_browser    - browser bridge gemini_pro_server :5555
#   ollama            - 100% local en :11434
LLM_PROVIDER = os.environ.get("JARVIS_LLM_PROVIDER", "openrouter").lower()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_LIGHT = os.environ.get("OPENROUTER_MODEL_LIGHT",
                                          "anthropic/claude-haiku-4.5")
OPENROUTER_MODEL_HEAVY = os.environ.get("OPENROUTER_MODEL_HEAVY",
                                          "anthropic/claude-sonnet-4.5")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_BROWSER_URL = os.environ.get("GEMINI_BROWSER_URL",
                                      "http://10.0.2.2:5555")
GEMINI_MODEL_DEFAULT = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL_DEFAULT = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")

# Triggers que detonan modelo PESADO (Sonnet) vs ligero (Haiku) en openrouter.
# Match por substring case-insensitive sobre (prompt + " " + system).upper().
HEAVY_TRIGGERS = [
    "MODO INGENIERO", "MODO ARQUITECTO", "MODO ARQUITECTO GOD-MODE",
    "GOD-MODE", "GOD MODE", "OPUS", "SONNET",
    "REFACTOR", "MODO GOD-MODE", "MODO PERSISTENCIA",
    "CRITICAL", "PRODUCTION CODE", "ARCHITECT MODE",
]


def is_heavy_prompt(prompt: str, system: str = "") -> bool:
    """Public helper: decide si un prompt necesita Sonnet (heavy) vs Haiku."""
    text = (prompt + " " + system).upper()
    return any(t in text for t in HEAVY_TRIGGERS)

# Fallback chain (Cascading Fallback): primary -> paid alternative -> proxy gratis -> local
# Si 402/429 en paid providers, salta a anthropic_proxy (OAuth Max plan, gratis pero lento).
_default_fallback_map = {
    "openrouter": "anthropic_proxy,gemini_api,ollama",
    "anthropic_proxy": "openrouter,gemini_api,ollama",
    "gemini_api": "anthropic_proxy,openrouter,ollama",
}
_default_fallback = _default_fallback_map.get(LLM_PROVIDER, "anthropic_proxy,ollama")
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


def _route_model(prompt: str, system: str) -> tuple[str, str]:
    """Decide modelo HEAVY o LIGHT segun:
      1. Keyword triggers explicitos (MODO INGENIERO, etc.)
      2. Tamano del prompt (>4000 chars sugiere tarea compleja)
      3. Patrones de codigo (def , class , import , triple backticks)
      4. Multiples lineas (>30 newlines)
    Devuelve (model_name, reason).
    """
    combined = prompt + "\n" + system
    text_upper = combined.upper()

    # 1. Keyword explicit
    for trigger in HEAVY_TRIGGERS:
        if trigger in text_upper:
            return OPENROUTER_MODEL_HEAVY, f"trigger:{trigger}"

    # 2. Tamano del prompt
    if len(prompt) > 4000:
        return OPENROUTER_MODEL_HEAVY, f"large_prompt:{len(prompt)}c"

    # 3. Codigo presente (suggests refactor/review)
    code_markers = ["def ", "class ", "import ", "```python", "```py"]
    code_hits = sum(combined.count(m) for m in code_markers)
    if code_hits >= 5:
        return OPENROUTER_MODEL_HEAVY, f"code_dense:{code_hits}_markers"

    # 4. Many lines
    nlines = combined.count("\n")
    if nlines > 30:
        return OPENROUTER_MODEL_HEAVY, f"multiline:{nlines}_lines"

    return OPENROUTER_MODEL_LIGHT, "default_light"


def _ask_openrouter(prompt: str, system: str, max_tokens: int,
                     timeout: int) -> str | None:
    """OpenRouter HTTP API con router dinamico Haiku<->Sonnet.

    Router inteligente _route_model() decide por keywords, longitud,
    densidad de codigo y multilinea. Cero RAM extra, sin CLI.
    """
    if not OPENROUTER_API_KEY:
        print("[brain] OPENROUTER_API_KEY no seteado", file=sys.stderr)
        return None
    model, route_reason = _route_model(prompt, system)
    print(f"[brain] openrouter -> {model} ({route_reason})", file=sys.stderr)
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Corgipollo/JarvisAI",
        "X-Title": "Jarvis V2",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                       headers=headers, json=payload, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise RuntimeError(f"openrouter: {data['error'].get('message', data['error'])}")
    return data["choices"][0]["message"]["content"]


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


def _is_fatal_provider_error(exc: Exception) -> bool:
    """402 Payment Required o 429 Rate Limited = no reintentar este provider,
    saltar al siguiente en la cascada. Retornar inmediatamente para no quemar
    tiempo + permitir cascading fallback rapido."""
    s = str(exc)
    return ("402" in s or "429" in s or "Payment Required" in s
            or "Too Many Requests" in s or "quota" in s.lower())


def _try_provider(provider: str, prompt: str, system: str, model: str,
                   max_tokens: int, timeout: int, retries: int) -> str | None:
    """Llama un provider especifico. Devuelve texto o None si falla."""
    if provider == "openrouter":
        for attempt in range(retries + 1):
            try:
                r = _ask_openrouter(prompt, system, max_tokens, timeout)
                if r:
                    return r
            except Exception as e:
                # Cascading fallback: 402/429 -> skip retries, saltar a next provider
                if _is_fatal_provider_error(e):
                    print(f"[brain] openrouter FATAL ({e}); switch a fallback",
                          file=sys.stderr)
                    return None
                if attempt < retries:
                    time.sleep(min(30, 5 * (2 ** attempt)))
                    continue
                print(f"[brain] openrouter fallo: {e}", file=sys.stderr)
        return None

    if provider == "gemini_api":
        for attempt in range(retries + 1):
            try:
                return _ask_gemini_api(prompt, system, max_tokens, timeout)
            except Exception as e:
                if _is_fatal_provider_error(e):
                    print(f"[brain] gemini_api FATAL ({e}); switch a fallback",
                          file=sys.stderr)
                    return None
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
        print("[brain.ask_claude_json] text vacio del LLM "
              f"(provider={LLM_PROVIDER}, prompt_head={prompt[:80]!r})",
              file=sys.stderr)
        return None
    # Extraer JSON si viene envuelto en ```json o texto
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        print(f"[brain.ask_claude_json] no JSON en respuesta. head: {text[:200]!r}",
              file=sys.stderr)
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(f"[brain.ask_claude_json] JSON inválido: {e}. raw head: {text[:200]!r}",
              file=sys.stderr)
        # Intento de cleanup comun: trailing comma, comillas mal
        cleaned = re.sub(r",\s*([\]}])", r"\1", m.group(0))
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def ping_proxy() -> bool:
    """Verifica que el proxy esta vivo."""
    try:
        r = requests.get(f"{PROXY}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


# ============================================================================
# ASYNC API (2026-05-25) - Para callers async puros (FastAPI endpoints).
# Sync API arriba (ask_claude/ask_claude_json) se mantiene para retro-compat
# con LangGraph/threads existentes. Migrar gradualmente.
# ============================================================================
import asyncio as _asyncio

_HTTPX_ASYNC: "httpx.AsyncClient | None" = None


def _async_client() -> "httpx.AsyncClient":
    global _HTTPX_ASYNC
    if _HTTPX_ASYNC is None:
        import httpx as _httpx
        _HTTPX_ASYNC = _httpx.AsyncClient(
            timeout=_httpx.Timeout(180.0, connect=10.0),
            limits=_httpx.Limits(max_keepalive_connections=10,
                                   max_connections=20,
                                   keepalive_expiry=300.0),
            http2=False,
        )
    return _HTTPX_ASYNC


async def ask_claude_async(
    prompt: str,
    system: str = "Eres Jarvis, asistente autonomo de Emmanuel. Respondes directo, sin preamble, en espanol.",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000,
    timeout: int = 180,
    retries: int = 2,
) -> str | None:
    """Version async puro via httpx.AsyncClient + claude_proxy_fast :8088.

    NO bloquea el event loop. Para usar desde FastAPI endpoints async def.
    Para callers sync existentes, sigue usando ask_claude() (proxy sync).
    """
    import httpx as _httpx
    payload = {"model": model, "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens}
    last_err = None
    for attempt in range(retries + 1):
        try:
            r = await _async_client().post(
                f"{PROXY}/v1/messages", json=payload, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            if "content" in data and isinstance(data["content"], list):
                for c in data["content"]:
                    if c.get("type") == "text":
                        return c.get("text", "")
            return None
        except _httpx.HTTPStatusError as e:
            last_err = f"http_{e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code in (429, 502, 503) and attempt < retries:
                await _asyncio.sleep(min(30, 5 * (2 ** attempt)))
                continue
            break
        except (_httpx.TimeoutException, _httpx.ConnectError) as e:
            last_err = f"net: {e}"
            if attempt < retries:
                await _asyncio.sleep(min(15, 3 * (2 ** attempt)))
                continue
        except Exception as e:
            last_err = f"unknown: {e}"
            break
    print(f"[brain.async] failed after {retries+1} attempts: {last_err}",
          file=sys.stderr)
    return None


async def ask_claude_json_async(
    prompt: str,
    schema_hint: str = "JSON estricto: {key: value}",
    system: str | None = None,
    **kwargs,
) -> dict | None:
    """Variante async de ask_claude_json. Espera JSON valido del LLM."""
    import re
    sys_prompt = (system or
                   f"Eres Jarvis. Respondes SOLO JSON valido, sin markdown. {schema_hint}")
    text = await ask_claude_async(prompt, system=sys_prompt, **kwargs)
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        cleaned = re.sub(r",\s*([\]}])", r"\1", m.group(0))
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


if __name__ == "__main__":
    if not ping_proxy():
        print("ERROR: proxy en :8088 no responde. Arranca claude_proxy.py primero.")
        sys.exit(1)

    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hola Jarvis, di que estas vivo."
    answer = ask_claude(q)
    print(answer or "(sin respuesta)")
