"""telegram_jarvis.py - Centro de Comando movil para Jarvis V2.

Recibe mensajes (texto o voz) en Telegram -> POST a /execute -> polling status
-> reply con resultado.

Setup:
  1. @BotFather en Telegram, /newbot, copia TOKEN
  2. setx TELEGRAM_BOT_TOKEN xxx
  3. setx TELEGRAM_ALLOWED_CHAT_ID tu_chat_id (whitelist anti spam)
  4. python -m jarvis_v2.bridges.telegram_jarvis

Comandos:
  /status   - estado de daemons + ultimo task
  /tasks    - lista 10 ultimos
  texto     - se interpreta como objective y se dispatcha
  voz       - faster-whisper transcribe + se dispatcha
"""
from __future__ import annotations

import json
import os
import sys
import time
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
ALLOWED_CHAT = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")
API_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:5000")
API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")

_TG_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
_HEADERS = {"X-Jarvis-Token": API_TOKEN, "Content-Type": "application/json"}


def tg_get(method: str, **params) -> dict:
    r = requests.get(f"{_TG_API}/{method}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def tg_send(chat_id: int | str, text: str, parse_mode: str | None = None):
    body = {"chat_id": chat_id, "text": text[:4000]}
    if parse_mode:
        body["parse_mode"] = parse_mode
    r = requests.post(f"{_TG_API}/sendMessage", json=body, timeout=30)
    return r.ok


def is_allowed(chat_id: int) -> bool:
    """Whitelist anti spam."""
    if not ALLOWED_CHAT:
        return True
    return str(chat_id) == str(ALLOWED_CHAT)


def transcribe_voice(file_id: str) -> str | None:
    """Descarga ogg voice + transcribe con faster-whisper."""
    try:
        info = tg_get("getFile", file_id=file_id)
        file_path = info["result"]["file_path"]
        url = f"https://api.telegram.org/file/bot{TELEGRAM_TOKEN}/{file_path}"
        ogg_local = ROOT / "data" / f"tg_voice_{int(time.time())}.ogg"
        ogg_local.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=60)
        ogg_local.write_bytes(r.content)
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="cpu", compute_type="int8")
        segments, _ = model.transcribe(str(ogg_local), language="es")
        text = " ".join(s.text for s in segments).strip()
        try:
            ogg_local.unlink()
        except Exception:
            pass
        return text
    except Exception as e:
        print(f"[tg] voice transcribe fail: {e}", file=sys.stderr)
        return None


def dispatch_objective(objective: str, chat_id: int) -> str:
    """POST /execute y poll status. Devuelve reporte para Telegram."""
    try:
        r = requests.post(f"{API_URL}/execute",
                          json={"objective": objective, "priority": 5},
                          headers=_HEADERS, timeout=30)
        r.raise_for_status()
        task_id = r.json().get("task_id")
        tg_send(chat_id, f"📥 Dispatched task {task_id}\nObjetivo: {objective[:200]}")

        # Poll
        for _ in range(120):
            time.sleep(4)
            t = requests.get(f"{API_URL}/tasks/{task_id}",
                             headers=_HEADERS, timeout=10).json()
            if t.get("status") not in ("queued", "running"):
                break
        status = t.get("status", "?")
        err = t.get("error", "")
        return (f"✅ Task {task_id}\n"
                f"Status: {status}\n"
                f"{('Error: ' + err) if err else 'Sin errores.'}")
    except Exception as e:
        return f"❌ Dispatch fail: {e}"


def handle_update(upd: dict):
    msg = upd.get("message") or upd.get("edited_message") or {}
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if not chat_id or not is_allowed(chat_id):
        return
    text = msg.get("text", "")
    voice = msg.get("voice")

    if text.startswith("/status"):
        try:
            h = requests.get(f"{API_URL}/health", timeout=5).json()
            tg_send(chat_id, f"🟢 Jarvis vivo\nTasks total: {h.get('total_tasks_lifetime')}\n"
                              f"Active: {h.get('active_tasks')}")
        except Exception as e:
            tg_send(chat_id, f"🔴 Jarvis API down: {e}")
        return

    if text.startswith("/tasks"):
        try:
            l = requests.get(f"{API_URL}/tasks?limit=10", headers=_HEADERS,
                             timeout=10).json()
            lines = [f"{t['task_id'][:8]} {t['status']} - {t['objective'][:60]}"
                     for t in l.get("tasks", [])]
            tg_send(chat_id, "Últimas tasks:\n" + "\n".join(lines) if lines
                    else "Sin tasks aún.")
        except Exception as e:
            tg_send(chat_id, f"Error: {e}")
        return

    if voice:
        tg_send(chat_id, "🎤 Transcribiendo voz...")
        text = transcribe_voice(voice["file_id"])
        if not text:
            tg_send(chat_id, "No pude transcribir, intenta de nuevo.")
            return
        tg_send(chat_id, f"📝 Transcripcion: {text[:200]}")

    if not text:
        return

    # Dispatch
    reply = dispatch_objective(text, chat_id)
    tg_send(chat_id, reply)


def main():
    if not TELEGRAM_TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN env no seteado")
        print("1. @BotFather en Telegram -> /newbot")
        print("2. setx TELEGRAM_BOT_TOKEN <token>")
        sys.exit(1)
    print(f"=== Jarvis Telegram bridge ===")
    print(f"  API: {API_URL}")
    print(f"  Whitelist chat: {ALLOWED_CHAT or '(anyone)'}")
    print(f"  Polling getUpdates...")
    offset = 0
    while True:
        try:
            r = tg_get("getUpdates", offset=offset, timeout=30)
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                try:
                    handle_update(upd)
                except Exception as e:
                    print(f"[tg] handle_update fail: {e}", file=sys.stderr)
        except KeyboardInterrupt:
            print("ciao")
            break
        except Exception as e:
            print(f"[tg] getUpdates error: {e}", file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    main()
