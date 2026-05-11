"""
claude_proxy.py — Proxy local Anthropic-compatible que usa Claude CLI subprocess.

Permite que UFO (y cualquier otro tool que use SDK Anthropic) consuma el
plan Claude Max via OAuth en lugar de gastar API key por token.

Endpoint compatible:
    POST /v1/messages   (Anthropic Messages API)

UFO config apunta a:
    API_TYPE: "claude"
    API_BASE: "http://localhost:8088/v1"
    API_KEY:  "fake-key-not-used"
    API_MODEL: "claude-sonnet-4-6"

Internamente:
    claude -p "<user_msg>" --system-prompt-file <tmp> --model claude-sonnet-4-6
       --dangerously-skip-permissions
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Claude CLI Proxy (Anthropic-compatible)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

CLAUDE_BIN = shutil.which("claude") or shutil.which("claude.cmd")
if not CLAUDE_BIN:
    raise RuntimeError("claude CLI no encontrado en PATH")

DEFAULT_MODEL = os.getenv("CLAUDE_PROXY_MODEL", "claude-sonnet-4-6")
TIMEOUT_S = int(os.getenv("CLAUDE_PROXY_TIMEOUT", "180"))


class MessageContent(BaseModel):
    type: str = "text"
    text: str | None = None


class Message(BaseModel):
    role: str
    content: str | list[dict]


class MessagesRequest(BaseModel):
    model: str | None = None
    messages: list[dict]
    system: str | list | None = None
    max_tokens: int = 4096
    temperature: float | None = None
    stream: bool = False


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for c in content:
            if isinstance(c, dict):
                if c.get("type") == "text":
                    out.append(c.get("text", ""))
                elif c.get("type") == "image":
                    out.append("[IMAGE]")
            elif isinstance(c, str):
                out.append(c)
        return "\n".join(out)
    return str(content)


def _system_text(system) -> str:
    if system is None:
        return ""
    if isinstance(system, str):
        return system
    if isinstance(system, list):
        return "\n".join(s.get("text", "") if isinstance(s, dict) else str(s) for s in system)
    return str(system)


def call_claude_cli(messages: list[dict], system: str, model: str, timeout: int) -> str:
    """Envia mensajes a Claude CLI. Solo el ULTIMO user message como prompt
    (Claude CLI no es multi-turn aware, lo trata como una sola request).
    History previa se inyecta al system_prompt como contexto.
    """
    # Separar history vs ultimo user
    last_user_text = ""
    history_parts = []
    for i, m in enumerate(messages):
        role = m.get("role", "user")
        text = _extract_text(m.get("content", ""))
        if i == len(messages) - 1 and role == "user":
            last_user_text = text
        else:
            history_parts.append(f"{role}: {text}")

    if not last_user_text:
        # Fallback: todo concat
        last_user_text = "\n\n".join(history_parts) or _extract_text(messages[-1].get("content", ""))

    # System prompt = system original + history previa (si existe)
    full_system = system or ""
    if history_parts:
        full_system += "\n\n=== CONVERSATION HISTORY ===\n" + "\n\n".join(history_parts)

    args = [CLAUDE_BIN, "-p", last_user_text,
            "--dangerously-skip-permissions",
            "--model", model]

    sys_file = None
    if full_system.strip():
        sys_file = tempfile.NamedTemporaryFile(
            mode="w", suffix="_sys.md", delete=False, encoding="utf-8"
        )
        sys_file.write(full_system)
        sys_file.close()
        args += ["--system-prompt-file", sys_file.name]

    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", shell=False,
        )
    finally:
        if sys_file:
            try: os.unlink(sys_file.name)
            except Exception: pass

    if proc.returncode != 0:
        raise HTTPException(500, f"claude CLI rc={proc.returncode}: {proc.stderr[:500]}")
    return proc.stdout.strip()


@app.post("/v1/messages")
async def messages_endpoint(req: MessagesRequest):
    model = req.model or DEFAULT_MODEL
    system = _system_text(req.system)

    try:
        text = call_claude_cli(req.messages, system, model, TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "claude CLI timeout")

    # Approx token count (Claude doesn't expose via CLI)
    approx_in = sum(len(_extract_text(m.get("content", ""))) for m in req.messages) // 4
    approx_out = len(text) // 4

    return {
        "id": f"msg_{uuid.uuid4().hex[:24]}",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": approx_in,
            "output_tokens": approx_out,
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
        },
    }


@app.get("/health")
async def health():
    return {"ok": True, "claude_bin": CLAUDE_BIN, "model": DEFAULT_MODEL}


@app.get("/")
async def root():
    return {
        "service": "claude-cli-proxy",
        "compatible_with": "anthropic v1",
        "endpoint": "/v1/messages",
        "note": "Usa Claude CLI con OAuth Max (gratis), no API key por token",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CLAUDE_PROXY_PORT", "8088"))
    print(f"Iniciando Claude proxy en http://localhost:{port}", flush=True)
    print(f"Claude binary: {CLAUDE_BIN}", flush=True)
    print(f"Default model: {DEFAULT_MODEL}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
