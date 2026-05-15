"""autorelaunch_watchdog.py - Si todos los brains mueren, relanza SOLO_ENTRENA.

Cada 2 min cuenta procesos python.exe que ejecutan algo de jarvis. Si baja
de un umbral critico, asume crash y relanza el bat. Asi si algun skill
destructivo cierra explorer/apps, Jarvis se recupera solo.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

JARVIS_BAT = ROOT / "SOLO_ENTRENA.bat"
LOG = ROOT / "data" / "autorelaunch.log"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    line = f"[autorelaunch {datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def count_jarvis_python_procs() -> int:
    """Cuenta procesos python.exe ejecutando algo dentro de C:\\Jarvis."""
    try:
        import psutil
    except ImportError:
        return 99  # Sin psutil, asumir todo OK
    count = 0
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if p.info["name"] and "python" in p.info["name"].lower():
                cmd = " ".join(p.info["cmdline"] or [])
                if any(k in cmd.lower() for k in
                       ["jarvis_learners", "jarvis_swarm", "jarvis_bridge",
                        "self_improvement", "watchdog", "coach.py",
                        "self_optimizer", "brain_opus", "brain_sonnet",
                        "brain_haiku", "unified_context"]):
                    count += 1
        except Exception:
            continue
    return count


def main():
    log("=== AUTORELAUNCH watchdog ARRANCADO ===")
    log("vigila procesos jarvis cada 2 min. Si <8, relanza SOLO_ENTRENA.bat")

    # Wait for initial swarm to settle
    time.sleep(120)

    consecutive_low = 0
    while True:
        try:
            n = count_jarvis_python_procs()
            log(f"jarvis python procs: {n}")
            if n < 8:
                consecutive_low += 1
                log(f"  bajo el umbral (consecutive_low={consecutive_low})")
                if consecutive_low >= 2:
                    log(f"  CRASH detectado, relanzando SOLO_ENTRENA.bat...")
                    try:
                        subprocess.Popen(
                            ["cmd.exe", "/c", "start", "", str(JARVIS_BAT)],
                            cwd=str(ROOT), shell=False,
                        )
                        log(f"  relanzado. Esperando 180s antes de proxima medicion")
                        time.sleep(180)
                        consecutive_low = 0
                    except Exception as e:
                        log(f"  error relanzando: {e}")
            else:
                consecutive_low = 0
        except Exception as e:
            log(f"error loop: {e}")
        time.sleep(120)


if __name__ == "__main__":
    main()
