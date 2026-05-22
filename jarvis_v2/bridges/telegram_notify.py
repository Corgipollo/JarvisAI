"""telegram_notify.py - Helper para que cualquier daemon notifique a Emmanuel.

Uso:
    from jarvis_v2.bridges.telegram_notify import notify
    notify("Acabe de subir 3 productos a Shopify")
    notify_file("Reporte horario", pdf_path)

NO arranca polling de getUpdates (eso lo hace telegram_jarvis.py).
Solo envia mensajes salientes.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_ALLOWED_CHAT_ID", "")


def _api(method: str) -> str:
    return f"https://api.telegram.org/bot{TOKEN}/{method}"


def notify(text: str, chat_id: str | None = None,
            parse_mode: str | None = None) -> bool:
    """Manda mensaje de texto. Devuelve True si OK."""
    if not TOKEN:
        return False
    cid = chat_id or CHAT_ID
    if not cid:
        return False
    try:
        body = {"chat_id": cid, "text": text[:4000]}
        if parse_mode:
            body["parse_mode"] = parse_mode
        r = requests.post(_api("sendMessage"), json=body, timeout=15)
        return r.ok
    except Exception as e:
        print(f"[tg_notify] fail: {e}", file=sys.stderr)
        return False


def notify_file(caption: str, file_path: str | Path,
                  chat_id: str | None = None) -> bool:
    """Envia un archivo (PDF, imagen, log, etc.) con caption."""
    if not TOKEN:
        return False
    cid = chat_id or CHAT_ID
    if not cid:
        return False
    fp = Path(file_path)
    if not fp.exists():
        return False
    try:
        with fp.open("rb") as f:
            files = {"document": (fp.name, f)}
            data = {"chat_id": cid, "caption": caption[:1024]}
            r = requests.post(_api("sendDocument"), data=data, files=files,
                              timeout=60)
            return r.ok
    except Exception as e:
        print(f"[tg_notify] file fail: {e}", file=sys.stderr)
        return False


def notify_photo(caption: str, image_path: str | Path,
                  chat_id: str | None = None) -> bool:
    """Envia una imagen con caption (compress automatica)."""
    if not TOKEN:
        return False
    cid = chat_id or CHAT_ID
    if not cid:
        return False
    fp = Path(image_path)
    if not fp.exists():
        return False
    try:
        with fp.open("rb") as f:
            files = {"photo": (fp.name, f)}
            data = {"chat_id": cid, "caption": caption[:1024]}
            r = requests.post(_api("sendPhoto"), data=data, files=files,
                              timeout=60)
            return r.ok
    except Exception:
        return False


def configured() -> bool:
    """True si hay token + chat_id seteados."""
    return bool(TOKEN and CHAT_ID)


if __name__ == "__main__":
    if not configured():
        print("ERROR: TELEGRAM_BOT_TOKEN o TELEGRAM_ALLOWED_CHAT_ID no seteados")
        sys.exit(1)
    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Test ping de Jarvis"
    ok = notify(msg)
    print("OK" if ok else "FAIL")
