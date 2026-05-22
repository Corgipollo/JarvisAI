"""claude_proxy_fast.py - Proxy OAuth raw HTTP (sin CLI subprocess).

Reemplaza claude_proxy.py que tenia ~40s latencia por cold start del CLI.
Este envia HTTP directo a api.anthropic.com/v1/messages usando el accessToken
del Claude Code CLI (extraido de ~/.claude/.credentials.json).

Latencia esperada: 1-3s por call (vs 40s anterior).
Costo: $0 (cuenta Claude Max plan).

Investigacion previa (research 2026-05-22):
  - accessToken sk-ant-oat01-* funciona como Bearer en endpoint estandar
  - refreshToken para auto-renovar (expira ~8h)
  - Triangulacion: docs Anthropic + meridian repo + claude-max-proxy-py + medium articles

Endpoint compatible:
    POST /v1/messages (Anthropic Messages API)

UFO/Jarvis config:
    API_TYPE: anthropic
    API_BASE: http://localhost:8088/v1
    API_KEY: cualquier-cosa
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

CREDS_PATH = Path(os.environ.get("CLAUDE_CREDS",
                                   str(Path.home() / ".claude" / ".credentials.json")))
ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
ANTHROPIC_TOKEN_REFRESH = "https://console.anthropic.com/v1/oauth/token"

DEFAULT_MODEL = os.environ.get("CLAUDE_PROXY_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_VERSION = os.environ.get("ANTHROPIC_VERSION", "2023-06-01")
ANTHROPIC_BETA = os.environ.get("ANTHROPIC_BETA", "oauth-2025-04-20")

app = FastAPI(title="Claude OAuth Proxy (raw HTTP, no CLI)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                    allow_headers=["*"])

# Connection pooling para baja latencia
_HTTPX_CLIENT: httpx.Client | None = None


def _client() -> httpx.Client:
    global _HTTPX_CLIENT
    if _HTTPX_CLIENT is None:
        _HTTPX_CLIENT = httpx.Client(
            timeout=httpx.Timeout(180.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=10,
                                 max_connections=20,
                                 keepalive_expiry=300.0),
            http2=False,
        )
    return _HTTPX_CLIENT


def _read_creds() -> dict:
    if not CREDS_PATH.exists():
        raise RuntimeError(f"credenciales no encontradas: {CREDS_PATH}")
    return json.loads(CREDS_PATH.read_text(encoding="utf-8"))


def _save_creds(data: dict):
    CREDS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get_access_token(force_refresh: bool = False) -> str:
    """Devuelve accessToken valido. Refresca si esta expirado."""
    creds = _read_creds()
    oauth = creds.get("claudeAiOauth", {})
    token = oauth.get("accessToken", "")
    expires_at = oauth.get("expiresAt", 0)  # ms unix

    now_ms = int(time.time() * 1000)
    margin_ms = 60 * 1000  # 1 min margin para evitar carrera

    if not force_refresh and token and now_ms < (expires_at - margin_ms):
        return token

    # Refresh
    refresh_token = oauth.get("refreshToken", "")
    if not refresh_token:
        raise RuntimeError("no refreshToken en credentials.json")

    print(f"[proxy] refrescando OAuth token...", file=sys.stderr)
    try:
        r = _client().post(
            ANTHROPIC_TOKEN_REFRESH,
            json={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": "9d1c250a-e61b-44d9-88ed-5944d1962f5e",
            },
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        raise RuntimeError(f"refresh OAuth fallo: {e}")

    new_token = data.get("access_token")
    new_refresh = data.get("refresh_token", refresh_token)
    expires_in = data.get("expires_in", 3600)  # seconds
    new_expires_at = now_ms + (expires_in * 1000)

    creds["claudeAiOauth"]["accessToken"] = new_token
    creds["claudeAiOauth"]["refreshToken"] = new_refresh
    creds["claudeAiOauth"]["expiresAt"] = new_expires_at
    _save_creds(creds)

    print(f"[proxy] token refrescado, expira en {expires_in}s", file=sys.stderr)
    return new_token


# Pydantic models compatible Anthropic API
class MessagesRequest(BaseModel):
    model: str | None = None
    messages: list[dict]
    system: str | list | None = None
    max_tokens: int = 4096
    temperature: float | None = None
    stream: bool = False
    tools: list | None = None


def _call_anthropic_with_retry(payload: dict) -> dict:
    """Call al endpoint Anthropic. Auto-refresca token si 401."""
    for attempt in range(2):
        token = _get_access_token(force_refresh=(attempt > 0))
        headers = {
            "Authorization": f"Bearer {token}",
            "anthropic-version": ANTHROPIC_VERSION,
            "anthropic-beta": ANTHROPIC_BETA,
            "content-type": "application/json",
            "user-agent": "claude-cli/1.0 (proxy)",
        }
        try:
            r = _client().post(ANTHROPIC_API, json=payload, headers=headers,
                                timeout=180.0)
            if r.status_code == 401 and attempt == 0:
                print(f"[proxy] 401, forcing refresh", file=sys.stderr)
                continue
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and attempt == 0:
                continue
            raise HTTPException(e.response.status_code,
                                  f"anthropic: {e.response.text[:500]}")
        except Exception as e:
            raise HTTPException(502, f"upstream: {e}")
    raise HTTPException(500, "max retries refresh")


@app.get("/health")
def health():
    try:
        creds = _read_creds()
        sub = creds.get("claudeAiOauth", {}).get("subscriptionType", "?")
        expires = creds.get("claudeAiOauth", {}).get("expiresAt", 0)
        expires_in_s = max(0, (expires - int(time.time() * 1000)) // 1000)
        return {"ok": True, "mode": "raw_http_oauth",
                "subscription": sub, "token_expires_in_s": expires_in_s,
                "default_model": DEFAULT_MODEL}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/v1/messages")
async def messages_endpoint(req: MessagesRequest):
    """Compatible con Anthropic SDK. Pasa al endpoint real con OAuth bearer."""
    payload = {
        "model": req.model or DEFAULT_MODEL,
        "messages": req.messages,
        "max_tokens": req.max_tokens,
    }
    if req.system:
        payload["system"] = req.system
    if req.temperature is not None:
        payload["temperature"] = req.temperature
    if req.tools:
        payload["tools"] = req.tools
    # No streaming por ahora (worker no lo procesa)

    t0 = time.time()
    data = _call_anthropic_with_retry(payload)
    dt = time.time() - t0
    print(f"[proxy] /v1/messages OK in {dt:.2f}s model={payload['model']}",
          file=sys.stderr)
    return data


@app.post("/v1/chat/completions")
async def openai_compat(req: dict):
    """Compat OpenAI. Traduce a Anthropic Messages format."""
    msgs = req.get("messages", [])
    system = None
    user_msgs = []
    for m in msgs:
        if m["role"] == "system":
            system = m["content"] if isinstance(m["content"], str) else \
                      "\n".join(p.get("text", "") for p in m["content"] if p.get("type") == "text")
        else:
            user_msgs.append(m)
    payload = {
        "model": req.get("model") or DEFAULT_MODEL,
        "messages": user_msgs,
        "max_tokens": req.get("max_tokens", 4096),
    }
    if system:
        payload["system"] = system
    data = _call_anthropic_with_retry(payload)
    # Convert response to OpenAI format
    text = ""
    if isinstance(data.get("content"), list):
        text = "\n".join(c.get("text", "") for c in data["content"]
                           if c.get("type") == "text")
    return {
        "id": data.get("id", ""),
        "object": "chat.completion",
        "model": data.get("model", payload["model"]),
        "choices": [{"index": 0, "finish_reason": data.get("stop_reason", "stop"),
                      "message": {"role": "assistant", "content": text}}],
        "usage": data.get("usage", {}),
    }


def main():
    import uvicorn
    port = int(os.environ.get("CLAUDE_PROXY_PORT", "8088"))
    host = os.environ.get("CLAUDE_PROXY_HOST", "0.0.0.0")
    print(f"=== claude_proxy_fast (raw HTTP OAuth) en {host}:{port} ===",
          flush=True)
    print(f"  creds: {CREDS_PATH}", flush=True)
    print(f"  default model: {DEFAULT_MODEL}", flush=True)
    try:
        creds = _read_creds()
        sub = creds.get("claudeAiOauth", {}).get("subscriptionType", "?")
        print(f"  subscription: {sub}", flush=True)
    except Exception as e:
        print(f"  WARN: {e}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
