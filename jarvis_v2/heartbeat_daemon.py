"""heartbeat_daemon.py - Boredom loop + autonomous ideation.

24/7 daemon. Si no hay actividad voz/usuario en 2 horas -> dispara
ideation_engine. Cada iteracion guarda status board.

NON-BLOCKING: ideation corre en thread separado. Si voice daemon detecta
comando, todo sigue funcionando.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

VOICE_ACTIVITY_LOG = ROOT / "data" / "voice_activity.log"
STATUS_BOARD = ROOT / "data" / "status_board.json"
HEARTBEAT_LOG = ROOT / "data" / "heartbeat.log"

BOREDOM_THRESHOLD_HOURS = float(os.environ.get("JARVIS_BOREDOM_HOURS", "2"))
CHECK_INTERVAL_SEC = 60  # check idle cada 1 min


def log(msg: str):
    line = f"[heartbeat {datetime.utcnow().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        HEARTBEAT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with HEARTBEAT_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def last_voice_activity() -> datetime | None:
    """Lee la marca de tiempo del ultimo comando de voz."""
    if not VOICE_ACTIVITY_LOG.exists():
        return None
    try:
        # Ultima linea no vacia
        lines = [l.strip() for l in VOICE_ACTIVITY_LOG.read_text(encoding="utf-8")
                 .splitlines() if l.strip()]
        if not lines:
            return None
        last = lines[-1]
        # Format: ISO timestamp en cada linea
        return datetime.fromisoformat(last.split(" ")[0])
    except Exception:
        return None


def is_bored() -> bool:
    """True si no ha habido actividad voz reciente."""
    last = last_voice_activity()
    if last is None:
        return True  # nunca hubo voz, asume bored
    elapsed = datetime.utcnow() - last
    return elapsed > timedelta(hours=BOREDOM_THRESHOLD_HOURS)


def run_ideation_in_thread():
    """Lanza ideation_engine en thread separado, no bloquea main loop."""
    def _worker():
        try:
            from jarvis_v2.core.ideation_engine import autonomous_iteration
            log(f"  ideation iteration starting")
            result = autonomous_iteration()
            log(f"  ideation done: status={result.get('status')}")
        except Exception as e:
            log(f"  ideation crashed: {type(e).__name__}: {e}")
    t = threading.Thread(target=_worker, daemon=False, name="ideation")
    t.start()
    return t


def update_status_idle(elapsed_h: float):
    """Marca el status board como idle/waiting."""
    STATUS_BOARD.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if STATUS_BOARD.exists():
        try:
            existing = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["last_check"] = datetime.utcnow().isoformat()
    existing["idle_hours"] = elapsed_h
    existing["heartbeat_alive"] = True
    STATUS_BOARD.write_text(json.dumps(existing, ensure_ascii=False, indent=2,
                                       default=str), encoding="utf-8")


def main():
    log(f"=== Heartbeat Daemon ARRANCADO ===")
    log(f"  boredom threshold: {BOREDOM_THRESHOLD_HOURS}h")
    log(f"  check interval: {CHECK_INTERVAL_SEC}s")
    log(f"  voice activity log: {VOICE_ACTIVITY_LOG}")

    last_ideation = None
    min_ideation_gap = timedelta(hours=1)  # no spawnear ideations mas seguido

    while True:
        try:
            last = last_voice_activity()
            now = datetime.utcnow()
            if last:
                elapsed_h = (now - last).total_seconds() / 3600
            else:
                elapsed_h = 999  # nunca voz = full idle

            update_status_idle(elapsed_h)

            if elapsed_h > BOREDOM_THRESHOLD_HOURS:
                # Bored! Check min gap entre ideations
                if (last_ideation is None or
                        now - last_ideation > min_ideation_gap):
                    log(f"BORED (idle {elapsed_h:.1f}h) -> launching ideation")
                    run_ideation_in_thread()
                    last_ideation = now
                else:
                    gap = min_ideation_gap - (now - last_ideation)
                    log(f"  bored pero cooldown activo, restantes "
                        f"{gap.total_seconds()/60:.0f}min")
        except Exception as e:
            log(f"  loop error: {e}")
        time.sleep(CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
