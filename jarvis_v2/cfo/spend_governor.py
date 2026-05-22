"""spend_governor.py - Daemon de seguridad de ultimo recurso.

Corre como Windows scheduled task / Linux systemd / cron. Lee SQLite
spend_ledger cada 1s. Si detecta anomalia, mata todos los procesos Jarvis
y escribe kill_marker para evitar restart loops (cooldown 24h).

7 fixes aplicados:
  1. Markers amplios (jarvis_v2, graph.py, cfo_evaluator)
  2. Poll 1s no 10s
  3. Telegram notification on kill
  4. kill_marker para cooldown (no restart loop)
  5. WAL mode + retry on locked
  6. Sin imports unused
  7. Notas para registrarse como Task Scheduler
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "spend_ledger.sqlite"
KILL_MARKER = ROOT / "data" / ".governor_killed_at"
GOVERNOR_LOG = ROOT / "data" / "governor.log"

# Hard caps - sobreescriben a constitution
MAX_HOURLY_SPEND = 5.00
MAX_DAILY_SPEND = 20.00
MAX_PER_INSERT = 5.00
MAX_API_CALLS_PER_MIN = 30

# Telegram (opcional, lee de env vars o file)
TG_TOKEN = os.environ.get("JARVIS_TG_TOKEN", "")
TG_CHAT = os.environ.get("JARVIS_TG_CHAT", "")

JARVIS_MARKERS = [
    "jarvis_v2", "graph.py", "cfo_evaluator",
    "skill_learner", "self_improvement", "auto_practice",
]


def log(msg: str):
    line = f"[{datetime.utcnow().isoformat()}] {msg}"
    print(line, flush=True)
    try:
        GOVERNOR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with GOVERNOR_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def alert(reason: str):
    """Telegram alert al kill - sin notificacion, kill silencioso es peligroso."""
    if not (TG_TOKEN and TG_CHAT):
        log(f"  (no telegram configured) reason={reason}")
        return
    try:
        import requests
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={
                "chat_id": TG_CHAT,
                "text": f"🚨 GOVERNOR KILL\n\nReason: {reason}\n"
                        f"Time: {datetime.utcnow().isoformat()}\n"
                        f"Cooldown: 24h\n\n"
                        f"Para reactivar: borra {KILL_MARKER}",
            },
            timeout=5,
        )
    except Exception as e:
        log(f"  telegram alert failed: {e}")


def write_kill_marker(reason: str, cooldown_hours: int = 24):
    KILL_MARKER.parent.mkdir(parents=True, exist_ok=True)
    KILL_MARKER.write_text(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "reason": reason,
        "cooldown_hours": cooldown_hours,
    }), encoding="utf-8")


def kill_jarvis(reason: str):
    log(f"🚨 CIRCUIT BREAKER: {reason}")
    write_kill_marker(reason)
    alert(reason)
    killed = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = " ".join(proc.info.get("cmdline") or [])
            name = (proc.info.get("name") or "").lower()
            if "python" not in name:
                continue
            if any(m in cmdline.lower() for m in JARVIS_MARKERS):
                # IMPORTANTE: no matar al governor mismo
                if "spend_governor" in cmdline:
                    continue
                proc.kill()
                killed.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    log(f"  killed PIDs: {killed}")


def check_ledger():
    if not LEDGER.exists():
        return
    try:
        from jarvis_v2.cfo.cost_oracle import _connect
        con = _connect()
        now = datetime.utcnow()

        # Hourly
        cutoff_1h = (now - timedelta(hours=1)).isoformat()
        hourly = float(con.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM spend WHERE ts>=?",
            (cutoff_1h,)).fetchone()[0])
        if hourly > MAX_HOURLY_SPEND:
            con.close()
            kill_jarvis(f"hourly_spend ${hourly:.2f} > ${MAX_HOURLY_SPEND}")
            return

        # Daily
        cutoff_24h = (now - timedelta(hours=24)).isoformat()
        daily = float(con.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM spend WHERE ts>=?",
            (cutoff_24h,)).fetchone()[0])
        if daily > MAX_DAILY_SPEND:
            con.close()
            kill_jarvis(f"daily_spend ${daily:.2f} > ${MAX_DAILY_SPEND}")
            return

        # Per-insert anomaly (un solo registro > MAX_PER_INSERT)
        cutoff_5m = (now - timedelta(minutes=5)).isoformat()
        max_single = con.execute(
            "SELECT COALESCE(MAX(amount_usd),0) FROM spend WHERE ts>=?",
            (cutoff_5m,)).fetchone()[0]
        if max_single > MAX_PER_INSERT:
            con.close()
            kill_jarvis(f"single_action_spend ${max_single} > ${MAX_PER_INSERT}")
            return

        # API call rate
        cutoff_1m = (now - timedelta(minutes=1)).isoformat()
        rate = con.execute(
            "SELECT COUNT(*) FROM spend WHERE ts>=?",
            (cutoff_1m,)).fetchone()[0]
        if rate > MAX_API_CALLS_PER_MIN:
            con.close()
            kill_jarvis(f"api_rate {rate}/min > {MAX_API_CALLS_PER_MIN}/min")
            return

        con.close()
    except sqlite3.OperationalError as e:
        # SQLite locked - retry next tick
        log(f"  sqlite locked, retry: {e}")


def main():
    log(f"=== Spend Governor iniciado ===")
    log(f"  ledger: {LEDGER}")
    log(f"  caps: ${MAX_HOURLY_SPEND}/h, ${MAX_DAILY_SPEND}/day, "
        f"${MAX_PER_INSERT}/action, {MAX_API_CALLS_PER_MIN} api/min")
    log(f"  telegram: {'ON' if TG_TOKEN else 'OFF'}")

    while True:
        try:
            check_ledger()
        except Exception as e:
            log(f"  error: {e}")
        time.sleep(1)  # Poll 1s (not 10s)


# Para registrar como Windows Scheduled Task:
# schtasks /Create /SC ONSTART /TN "JarvisSpendGovernor" /TR
#   "python.exe C:\\Users\\Emmanuel\\Documents\\JarvisAI\\jarvis_v2\\cfo\\spend_governor.py"
#   /RU SYSTEM /RL HIGHEST /F


if __name__ == "__main__":
    main()
