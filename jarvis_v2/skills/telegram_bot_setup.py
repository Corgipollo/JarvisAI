"""telegram_bot_setup.py - Skill autonoma para que Jarvis se saque su propio
bot de Telegram via @BotFather.

Estrategia: usa browser_cdp para hablar con Telegram Web (web.telegram.org)
que es el camino menos friccionado. Solo funciona si:
  1. Brave esta abierto con CDP en :9222 (ya activo en este host)
  2. Telegram Web esta logueado en una pestana O el usuario lo abre

Flujo:
  1. Abre pestana en https://web.telegram.org/k/
  2. Busca @BotFather en search box
  3. Click BotFather
  4. Tipea /newbot
  5. Espera prompt "Alright..."
  6. Tipea nombre: "Jarvis V2 Bot"
  7. Tipea username: "jarvis_emmanuel_v2_bot" (incrementa numero si tomado)
  8. Captura el token de la respuesta
  9. Setea env var via subprocess setx + .env update
  10. Reinicia telegram bridge daemon

Devuelve: dict con token (si lo extrajo), status, next_steps.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read_chat_visible_text(page) -> str:
    """Lee el texto visible del area de mensajes en Telegram Web."""
    try:
        return page.evaluate("""() => {
            const msgs = document.querySelectorAll('.message, .bubble');
            return Array.from(msgs).slice(-10).map(m => m.innerText).join('\\n---\\n');
        }""")
    except Exception:
        return ""


def _wait_for_text(page, needle: str, timeout_s: int = 30) -> bool:
    """Polea el chat hasta ver el texto esperado."""
    for _ in range(timeout_s):
        t = _read_chat_visible_text(page)
        if needle.lower() in (t or "").lower():
            return True
        time.sleep(1)
    return False


def setup_telegram_bot(bot_name: str = "Jarvis V2",
                        bot_username_base: str = "jarvis_emmanuel_v2") -> dict:
    """Auto-saca un bot Telegram via @BotFather en Telegram Web.

    REQUIERE: Brave abierto con CDP :9222 + Telegram Web logueado.
    """
    try:
        from jarvis_v2.skills import browser_cdp
    except ImportError as e:
        return {"ok": False, "error": f"browser_cdp no disponible: {e}"}

    p, browser, ctx, page = browser_cdp.attach()
    try:
        # 1. Buscar pestana Telegram Web abierta o abrir una
        tg_page = None
        for pg in ctx.pages:
            if "telegram.org" in pg.url:
                tg_page = pg
                break
        if not tg_page:
            tg_page = ctx.new_page()
            tg_page.goto("https://web.telegram.org/k/", timeout=20000)
            time.sleep(5)

        tg_page.bring_to_front()
        time.sleep(2)

        # Detectar si esta logueado: si vemos "Log in" -> no
        body_text = tg_page.evaluate("() => document.body.innerText[:1000]")
        if "Log in by phone" in body_text or "QR code" in body_text:
            return {
                "ok": False,
                "error": "telegram_not_logged_in",
                "action_required": (
                    "Abre web.telegram.org/k/ en tu Brave y loguea con QR o "
                    "phone. Despues re-dispatcha esta skill."
                ),
            }

        # 2. Buscar @BotFather en search
        search_selector = "input[placeholder*='Search']"
        tg_page.locator(search_selector).first.fill("BotFather")
        time.sleep(2)
        # Click primer resultado
        botfather_result = tg_page.locator(
            "div.search-result, li[data-peer-id*='botfather']"
        ).first
        botfather_result.click(timeout=10000)
        time.sleep(2)

        # 3. /newbot
        input_selector = "div.input-message-input, textarea[placeholder*='Message']"
        msg_input = tg_page.locator(input_selector).first
        msg_input.fill("/newbot")
        time.sleep(0.5)
        tg_page.keyboard.press("Enter")
        if not _wait_for_text(tg_page, "what to call", timeout_s=15):
            return {"ok": False, "error": "botfather_no_response_to_newbot"}

        # 4. Nombre del bot
        msg_input.fill(bot_name)
        tg_page.keyboard.press("Enter")
        if not _wait_for_text(tg_page, "username", timeout_s=15):
            return {"ok": False, "error": "botfather_no_response_to_name"}

        # 5. Username (intentar variantes si esta tomado)
        for suffix in ("_bot", "_v2_bot", "_pro_bot", "_alpha_bot"):
            uname = bot_username_base + suffix
            msg_input.fill(uname)
            tg_page.keyboard.press("Enter")
            time.sleep(3)
            t = _read_chat_visible_text(tg_page)
            if "taken" in t.lower() or "already" in t.lower():
                continue
            if "token" in t.lower() or re.search(r"\d{9,}:[A-Za-z0-9_-]{30,}", t):
                break
        else:
            return {"ok": False, "error": "all_usernames_taken"}

        # 6. Extraer token: pattern <digits>:<chars>
        chat_text = _read_chat_visible_text(tg_page)
        match = re.search(r"(\d{9,10}:[A-Za-z0-9_-]{30,})", chat_text)
        if not match:
            return {"ok": False, "error": "token_not_found_in_response",
                    "chat_tail": chat_text[-500:]}
        token = match.group(1)

        # 7. Persistir token en .env + setx
        env_path = ROOT / ".env"
        env_content = ""
        if env_path.exists():
            env_content = env_path.read_text(encoding="utf-8")
        # Update or append
        if "TELEGRAM_BOT_TOKEN=" in env_content:
            env_content = re.sub(r"TELEGRAM_BOT_TOKEN=.*",
                                  f"TELEGRAM_BOT_TOKEN={token}", env_content)
        else:
            env_content += f"\nTELEGRAM_BOT_TOKEN={token}\n"
        env_path.write_text(env_content, encoding="utf-8")

        # setx para persistencia Windows registry
        subprocess.run(["setx", "TELEGRAM_BOT_TOKEN", token],
                       capture_output=True, shell=True)

        return {
            "ok": True,
            "token": token[:20] + "...",  # No exponer entero en logs
            "bot_username": uname,
            "saved_to": str(env_path),
            "next_step": (
                "Setear TELEGRAM_ALLOWED_CHAT_ID (sacar de @userinfobot) y "
                "arrancar python -m jarvis_v2.bridges.telegram_jarvis"
            ),
        }
    finally:
        p.stop()


if __name__ == "__main__":
    print("=== telegram bot setup (auto) ===")
    r = setup_telegram_bot()
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2))
