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

DEFAULT_MODEL = os.getenv("CLAUDE_PROXY_MODEL", "claude-haiku-4-5-20251001")
TIMEOUT_S = int(os.getenv("CLAUDE_PROXY_TIMEOUT", "120"))


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


# =============================================================================
# MEMORIA PERSISTENTE (simula chat continuo entre llamadas)
# =============================================================================
MEMORY_FILE = Path(__file__).resolve().parents[1] / "data" / "claude_persistent_memory.jsonl"
MEMORY_LAST_N = 20  # ultimas N interacciones se inyectan como contexto


def _load_recent_memory() -> str:
    """Lee las ultimas N entradas del memory file y formatea como contexto."""
    if not MEMORY_FILE.exists():
        return ""
    try:
        lines = MEMORY_FILE.read_text(encoding="utf-8").splitlines()[-MEMORY_LAST_N:]
    except Exception:
        return ""
    parts = []
    for line in lines:
        try:
            entry = json.loads(line)
            parts.append(f"[USER@{entry.get('ts','?')[:19]}]: {entry.get('user','')[:300]}")
            parts.append(f"[CLAUDE]: {entry.get('claude','')[:500]}")
        except Exception:
            continue
    return "\n".join(parts)


def _save_memory(user_text: str, claude_text: str, session_id: str | None = None):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "session_id": session_id or "default",
        "user": user_text[:2000],
        "claude": claude_text[:5000],
    }
    try:
        with MEMORY_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


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

    # Instruccion compacta para Haiku (rapido + suficiente)
    if "FAST_INSTRUCTION" not in full_system:
        full_system = (
            "FAST_INSTRUCTION: Responde DIRECTO y CONCISO. Sin preamble. JSON cuando se pida.\n\n"
            + full_system
        )

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

    # Sandbox cwd: aisla el state local del CLI (~/.claude/projects/<cwd-hash>)
    # asi el proxy NO colisiona con sesiones Claude Code abiertas en otros cwd
    # (fix recomendado por Gemini 2026-05-21).
    sandbox_cwd = os.environ.get("CLAUDE_PROXY_SANDBOX_CWD", r"C:\Jarvis_Sandbox")
    try:
        os.makedirs(sandbox_cwd, exist_ok=True)
    except Exception:
        sandbox_cwd = None
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace", shell=False,
            cwd=sandbox_cwd,
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

    # MEMORIA PERSISTENTE: inyectar contexto previo si NO hay opt-out
    if os.getenv("CLAUDE_PROXY_NO_MEMORY") != "1":
        recent = _load_recent_memory()
        if recent:
            system = (system + "\n\n=== MEMORIA PERSISTENTE (chat continuo de Jarvis) ===\n"
                      + recent + "\n=== FIN MEMORIA ===").strip()

    try:
        text = call_claude_cli(req.messages, system, model, TIMEOUT_S)
    except subprocess.TimeoutExpired:
        raise HTTPException(504, "claude CLI timeout")

    # Guardar la interaccion en memoria (ultimo user + response)
    try:
        last_user = ""
        for m in reversed(req.messages):
            if m.get("role") == "user":
                last_user = _extract_text(m.get("content", ""))
                break
        if last_user:
            _save_memory(last_user, text)
    except Exception:
        pass

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
