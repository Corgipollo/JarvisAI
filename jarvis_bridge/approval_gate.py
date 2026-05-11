"""approval_gate.py — Gate de aprobación para acciones $$$ vía Telegram.

Antes de ejecutar acciones potencialmente destructivas (mandar email, borrar
archivo, postear redes, gastar API tokens caros), Jarvis manda preview a
Telegram y espera aprobación con 👍 / 👎.

Categorías de acciones que requieren approval:
  - 'destructive': borrar archivo/carpeta, taskkill, modificar registro
  - 'communication': mandar email, mensaje WhatsApp, post redes
  - 'financial': gastar > $X en API, transferencias, compras
  - 'irreversible': git push --force, drop database, formatear

Uso:
    from jarvis_bridge.approval_gate import request_approval
    approved = await request_approval(
        action="mandar email a alejandro@x.com",
        category="communication",
        preview="Subject: Reunion 5pm\\nBody: confirmamos para las 5...",
        timeout_seconds=300,
    )
    if approved:
        send_email(...)
    else:
        log("rechazado por usuario o timeout")
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

import requests

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config_telegram.json"
PENDING_DIR = ROOT / "data" / "approvals_pending"
DECIDED_DIR = ROOT / "data" / "approvals_decided"


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _send_telegram(text: str, chat_id: int, token: str) -> Optional[int]:
    """Manda mensaje con botones inline. Devuelve message_id."""
    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Aprobar", "callback_data": "approve"},
            {"text": "❌ Rechazar", "callback_data": "reject"},
        ]]
    }
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "reply_markup": keyboard,
            },
            timeout=10,
        )
        r.raise_for_status()
        return r.json()["result"]["message_id"]
    except Exception:
        return None


def _poll_decision(message_id: int, token: str, timeout_s: float) -> Optional[bool]:
    """Poll updates en busca de la decisión (callback_query con approve/reject)."""
    start = time.time()
    offset = 0
    while time.time() - start < timeout_s:
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{token}/getUpdates",
                params={"offset": offset, "timeout": 10},
                timeout=15,
            )
            r.raise_for_status()
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                cq = upd.get("callback_query")
                if cq and cq.get("message", {}).get("message_id") == message_id:
                    data = cq.get("data")
                    # Confirmar respuesta
                    requests.post(
                        f"https://api.telegram.org/bot{token}/answerCallbackQuery",
                        json={"callback_query_id": cq["id"]},
                        timeout=5,
                    )
                    return data == "approve"
        except Exception:
            time.sleep(3)
    return None


async def request_approval(action: str, category: str, preview: str,
                            timeout_seconds: float = 300) -> bool:
    """Pide aprobación al user via Telegram. Si auto-approve está set, salta."""
    cfg = _load_config()
    token = cfg.get("bot_token")
    chat_id = cfg.get("admin_chat_id") or (cfg.get("allowed_user_ids") or [None])[0]

    # Auto-approve para categorías marcadas seguras en config
    auto_ok = cfg.get("auto_approve_categories", [])
    if category in auto_ok:
        return True

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DECIDED_DIR.mkdir(parents=True, exist_ok=True)

    if not token or not chat_id:
        # Sin Telegram → log + reject por defecto (safe)
        pending = PENDING_DIR / f"req_{int(time.time())}.json"
        pending.write_text(json.dumps({
            "action": action, "category": category, "preview": preview,
            "ts": time.time(), "decided": "auto_reject_no_telegram",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return False

    text = (
        f"🤖 *Jarvis pide aprobación*\n\n"
        f"*Acción:* {action}\n"
        f"*Categoría:* `{category}`\n\n"
        f"*Preview:*\n```\n{preview[:500]}\n```\n\n"
        f"Decide en {int(timeout_seconds)}s."
    )

    msg_id = _send_telegram(text, chat_id, token)
    if not msg_id:
        return False

    loop = asyncio.get_event_loop()
    decision = await loop.run_in_executor(
        None, _poll_decision, msg_id, token, timeout_seconds
    )

    # Log
    decided_file = DECIDED_DIR / f"req_{int(time.time())}.json"
    decided_file.write_text(json.dumps({
        "action": action, "category": category, "preview": preview,
        "decision": decision, "ts": time.time(),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    return bool(decision)


def request_approval_sync(action: str, category: str, preview: str,
                          timeout_seconds: float = 300) -> bool:
    """Versión síncrona para llamar desde código no-async."""
    return asyncio.run(request_approval(action, category, preview, timeout_seconds))


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    if len(sys.argv) < 2:
        print("Test: python approval_gate.py test")
        sys.exit(0)

    if sys.argv[1] == "test":
        ok = request_approval_sync(
            action="test ping",
            category="test",
            preview="esto es un test del approval gate",
            timeout_seconds=60,
        )
        print(f"resultado: {ok}")
