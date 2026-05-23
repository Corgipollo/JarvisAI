"""monitor_swing.py - Verifica swing_hunter.db cada N min.

Si 0 trades en ventana_min, alerta Telegram y opcionalmente reinicia el
proceso swing_hunter_pro (clock drift Binance -1021 lo deja zombie).

Disenado para correr via Windows Task Scheduler cada 30 min.

Logs: data/monitor_swing.log
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DB_PATH = Path(
    r"C:\Users\Emmanuel\Documents\CerebroEmmanuel\BotForexV8-COMPLETO\bot"
    r"\swing_hunter.db"
)
LOG = ROOT / "data" / "monitor_swing.log"
WINDOW_MIN = int(os.environ.get("MONITOR_SWING_WINDOW_MIN", "30"))


def _log(msg: str):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[monitor_swing {ts}] {msg}", flush=True)


def count_recent_trades(window_min: int) -> int:
    """Cuenta trades en swing_hunter.db con entry_ts > (now - window_min)."""
    if not DB_PATH.exists():
        _log(f"FAIL db not found: {DB_PATH}")
        return -1
    cutoff_ms = int((time.time() - window_min * 60) * 1000)
    cutoff_s = int(time.time() - window_min * 60)
    try:
        conn = sqlite3.connect(str(DB_PATH), timeout=10)
        cur = conn.cursor()
        # entry_ts puede estar en s o ms; probamos ambos
        cur.execute("SELECT COUNT(*) FROM trades WHERE entry_ts > ?", (cutoff_ms,))
        n_ms = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM trades WHERE entry_ts > ?", (cutoff_s,))
        n_s = cur.fetchone()[0]
        conn.close()
        return max(n_ms, n_s)
    except Exception as e:
        _log(f"db read error: {e}")
        return -1


def notify_telegram(text: str) -> bool:
    """Best-effort notify. Silent fail si token absent."""
    try:
        from jarvis_v2.bridges.telegram_notify import notify
        return notify(text)
    except Exception as e:
        _log(f"telegram fail: {e}")
        return False


def restart_swing_hunter_pro() -> bool:
    """Intenta reiniciar swing_hunter_pro.py. Best-effort.

    Politica AGI: si esta running pero no tradea (clock drift), matamos y
    Windows watchdog del bot tipicamente lo levanta. Si no, lo arrancamos
    nosotros.
    """
    try:
        # Mata si vive
        ps = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
             "Where-Object { $_.CommandLine -match 'swing_hunter_pro' } | "
             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"],
            capture_output=True, text=True, timeout=15,
        )
        _log(f"kill: rc={ps.returncode}")

        # Force NTP resync antes de relanzar
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "w32tm /resync /force"],
            capture_output=True, text=True, timeout=15,
        )
        _log("NTP resync forced before restart")

        # Relanza
        script = (
            r"C:\Users\Emmanuel\Documents\CerebroEmmanuel\BotForexV8-COMPLETO"
            r"\bot\swing_hunter_pro.py"
        )
        if not Path(script).exists():
            _log(f"script missing: {script}")
            return False
        subprocess.Popen(
            ["C:\\CPython310\\python.exe", script],
            cwd=Path(script).parent,
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        _log("relaunched swing_hunter_pro")
        return True
    except Exception as e:
        _log(f"restart error: {e}")
        return False


def main():
    n = count_recent_trades(WINDOW_MIN)
    _log(f"trades_in_last_{WINDOW_MIN}min={n}")
    if n == -1:
        return  # error de DB, ya logueado
    if n == 0:
        # 0 trades en la ventana - revisar fuera de horario o problema
        # heuristica: solo alertar si es horario hábil (UTC 6-22 cubre US+EU+Asia mix)
        hour_utc = datetime.utcnow().hour
        active_hours = 6 <= hour_utc <= 22
        msg = (
            f"swing_hunter 0 trades ultimos {WINDOW_MIN}min "
            f"(UTC hour={hour_utc}, active={active_hours}). "
            f"DB: {DB_PATH.name}"
        )
        if active_hours:
            notify_telegram(msg + " - reintentando con NTP resync + restart")
            restart_swing_hunter_pro()
        else:
            _log("fuera de horario activo, no restart")
    else:
        _log(f"OK {n} trades en ventana - swing_hunter vivo")


if __name__ == "__main__":
    main()
