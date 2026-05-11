"""telegram_bot.py — Conector Telegram para Jarvis.

Emmanuel manda mensajes a @TradinEmmanuelPedrazaBOT (o el bot configurado)
y Jarvis los procesa via queue_manager.

Flow:
  1. User: "edita este video con CapCut y hazme 10 cortes"
  2. Bot recibe → crea task en queue_manager
  3. jarvis_core.loop la procesa (cuando este en VM): busca skill en library,
     si no existe → skill_learner aprende → ejecuta
  4. Result → bot responde al user con summary + path archivos generados

Auth: token via env var TELEGRAM_BOT_TOKEN o config_telegram.json
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CONFIG_FILE = ROOT / "config_telegram.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "allowed_user_ids": [],  # list of user ids permitted
        "default_priority": 7,
    }


try:
    from telegram import Update, BotCommand
    from telegram.ext import (
        ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes,
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False


from jarvis_core import queue_manager                            # noqa: E402


def is_allowed(user_id: int, cfg: dict) -> bool:
    allowed = cfg.get("allowed_user_ids", [])
    if not allowed:
        return True  # if empty list, allow all (dev mode)
    return user_id in allowed


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Jarvis activo.\n\n"
        "Mandame una tarea y la encolo:\n"
        "  - 'edita este video con CapCut y hazme 10 cortes'\n"
        "  - 'busca tutoriales de X y aprende'\n"
        "  - 'abre Spotify'\n\n"
        "/queue — ver tareas pendientes\n"
        "/skills — ver biblioteca de skills aprendidas\n"
        "/status — estado del sistema"
    )


async def cmd_queue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stats = queue_manager.stats()
    items = queue_manager.list_tasks()[-10:]
    msg = f"📋 *Cola:*\n"
    msg += f"  pending: {stats['pending']}\n  in_progress: {stats['in_progress']}\n"
    msg += f"  completed: {stats['completed']}\n  failed: {stats['failed']}\n\n"
    if items:
        msg += "*Últimas 10:*\n"
        for t in reversed(items[-10:]):
            emoji = {"pending": "⏳", "in_progress": "🔄",
                     "completed": "✅", "failed": "❌"}.get(t["status"], "❓")
            msg += f"  {emoji} `{t['id']}` {t['text'][:60]}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_skills(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    skills_dir = ROOT / "data" / "skill_library"
    if not skills_dir.exists():
        await update.message.reply_text("Sin skills aún.")
        return
    idx_file = skills_dir / "_index.jsonl"
    if not idx_file.exists():
        await update.message.reply_text("Sin skills indexadas.")
        return
    skills = []
    for line in idx_file.read_text(encoding="utf-8").splitlines():
        try:
            skills.append(json.loads(line))
        except Exception:
            continue
    msg = f"🧠 *Skills aprendidas: {len(skills)}*\n\n"
    for s in skills[-15:]:
        msg += f"  • `{s['domain']}` {s['name']}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    live_state = ROOT / "data" / "jarvis_live_state.json"
    if live_state.exists():
        s = json.loads(live_state.read_text(encoding="utf-8"))
        expr = s.get("expression", {})
        msg = f"⚡ *Estado:* {expr.get('label','?')} {expr.get('emoji','')}\n"
        msg += f"📋 Queue: {s.get('queue_stats',{}).get('pending',0)} pendientes\n"
        if s.get("current_task"):
            msg += f"🔄 Procesando: {s['current_task'].get('text','')[:80]}\n"
    else:
        msg = "Sistema sin estado live (loop no corre todavia)."
    await update.message.reply_text(msg, parse_mode="Markdown")


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    cfg = load_config()
    user_id = update.effective_user.id
    if not is_allowed(user_id, cfg):
        await update.message.reply_text("⛔ User no autorizado")
        return
    text = update.message.text.strip()
    if not text:
        return
    task = queue_manager.add_task(
        text=text, source=f"telegram:{user_id}",
        priority=cfg.get("default_priority", 7),
    )
    await update.message.reply_text(
        f"✅ Tarea encolada: `{task['id']}`\n"
        f"   {text[:100]}\n\n"
        f"Te aviso cuando termine.",
        parse_mode="Markdown",
    )


async def post_init(app):
    await app.bot.set_my_commands([
        BotCommand("start", "Inicio"),
        BotCommand("queue", "Ver cola de tareas"),
        BotCommand("skills", "Skills aprendidas"),
        BotCommand("status", "Estado del sistema"),
    ])


def main():
    if not HAS_TELEGRAM:
        print("python-telegram-bot no instalado")
        print("  pip install python-telegram-bot")
        sys.exit(1)
    cfg = load_config()
    token = cfg.get("bot_token", "")
    if not token:
        print("Falta token. Setea TELEGRAM_BOT_TOKEN env var o config_telegram.json")
        sys.exit(1)
    app = ApplicationBuilder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("queue", cmd_queue))
    app.add_handler(CommandHandler("skills", cmd_skills))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    print("Bot iniciando... Escuchando mensajes.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
