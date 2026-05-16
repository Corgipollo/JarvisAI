"""orchestrator.py - Async swarm coordinator de Jarvis v2.

Patron: asyncio + worker tasks corriendo concurrent. gui_mouse_lock global
protege el mouse fisico (recurso unico). CFO sigue gateway antes de gastar.

Workers:
  - secretary_worker: navegacion visual social media (usa gui_lock)
  - creative_worker: After Effects ExtendScript + CLI render (mayormente sin gui_lock)
  - sentinel_worker: monitoreo de logs/metricas (no usa gui)

Cada worker:
  - Lee de su asyncio.Queue
  - Escribe estado a data/status_board.json (atomic)
  - Loggea voice_activity para que heartbeat sepa que NO esta idle
"""
from __future__ import annotations

import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATUS_BOARD = ROOT / "data" / "status_board.json"
VOICE_ACTIVITY_LOG = ROOT / "data" / "voice_activity.log"

# Queue compartida — cualquier daemon puede empujar tareas
TASK_QUEUE: asyncio.Queue = asyncio.Queue()


def write_status(department: str, payload: dict):
    """Append department status atomicamente. Multi-worker safe."""
    STATUS_BOARD.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if STATUS_BOARD.exists():
        try:
            existing = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
        except Exception:
            pass
    departments = existing.get("departments", {})
    departments[department] = {
        "ts": datetime.utcnow().isoformat(),
        **payload,
    }
    existing["departments"] = departments
    existing["last_update"] = datetime.utcnow().isoformat()
    tmp = STATUS_BOARD.with_suffix(".tmp")
    tmp.write_text(json.dumps(existing, ensure_ascii=False, indent=2,
                              default=str), encoding="utf-8")
    try:
        tmp.replace(STATUS_BOARD)
    except Exception:
        if STATUS_BOARD.exists():
            STATUS_BOARD.unlink()
        tmp.rename(STATUS_BOARD)


def log_activity(text: str):
    """Append to voice_activity.log so heartbeat sabe que NO esta idle."""
    try:
        VOICE_ACTIVITY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with VOICE_ACTIVITY_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()} [swarm] {text[:200]}\n")
    except Exception:
        pass


async def secretary_loop(stop_event: asyncio.Event,
                          poll_interval_min: int = 10):
    """Departamento Comercial: cada N min escanea redes y contesta."""
    from jarvis_v2.swarm.secretary_worker import scan_and_reply
    write_status("secretary", {"status": "starting", "platform": "init"})

    while not stop_event.is_set():
        try:
            # CFO check: cada ciclo cuesta tiempo de Claude. Pre-flight check.
            result = await asyncio.to_thread(scan_and_reply)
            write_status("secretary", {
                "status": "idle" if not result.get("replied_count") else "active",
                "platform": result.get("platform", "?"),
                "last_replies": result.get("replied_count", 0),
                "errors": result.get("errors", []),
            })
            log_activity(f"secretary cycle: replied={result.get('replied_count', 0)}")
        except Exception as e:
            write_status("secretary", {"status": "error",
                                       "error": f"{type(e).__name__}: {e}"})
        # Espera entre ciclos (no constante para parecer humano)
        import random
        jitter = random.uniform(0.8, 1.4)
        await asyncio.sleep(poll_interval_min * 60 * jitter)


async def creative_loop(stop_event: asyncio.Event):
    """Director Creativo: consume queue de ordenes de video."""
    from jarvis_v2.swarm.creative_worker import render_from_template
    write_status("creative", {"status": "waiting_orders"})
    while not stop_event.is_set():
        try:
            # Bloquea esperando orden con timeout para checar stop_event
            order = await asyncio.wait_for(TASK_QUEUE.get(), timeout=5)
        except asyncio.TimeoutError:
            continue
        if order.get("department") != "creative":
            # Reencolar para otro dept
            await TASK_QUEUE.put(order)
            await asyncio.sleep(0.5)
            continue
        write_status("creative", {"status": "rendering",
                                   "objective": order.get("objective", "")[:80]})
        try:
            result = await asyncio.to_thread(render_from_template, order)
            write_status("creative", {"status": "rendered_ok"
                                       if result.get("ok") else "render_failed",
                                       "output_file": result.get("output_file", ""),
                                       "duration_s": result.get("duration_s", 0)})
            log_activity(f"creative render: {result.get('output_file', '?')}")
        except Exception as e:
            write_status("creative", {"status": "error",
                                       "error": f"{type(e).__name__}: {e}"})
        TASK_QUEUE.task_done()


async def sentinel_loop(stop_event: asyncio.Event, interval_s: int = 30):
    """Monitoreo pasivo: status_board, ledger, heartbeat - sin GUI."""
    from jarvis_v2.cfo.cost_oracle import ledger_snapshot
    while not stop_event.is_set():
        snap = ledger_snapshot()
        write_status("sentinel", {
            "status": "monitoring",
            "budget_remaining_usd": max(0, 100 - snap.get("lifetime_spent_usd", 0)),
            "spent_24h": snap.get("spent_last_24h_usd", 0),
            "spent_1h": snap.get("spent_last_1h_usd", 0),
        })
        await asyncio.sleep(interval_s)


class SwarmOrchestrator:
    def __init__(self, enable: dict | None = None):
        self.stop_event = asyncio.Event()
        # Default: enable all departments
        self.enable = enable or {"secretary": True, "creative": True,
                                  "sentinel": True}

    def request_stop(self):
        print("[swarm] stop requested", flush=True)
        self.stop_event.set()

    async def run(self):
        tasks = []
        if self.enable.get("sentinel"):
            tasks.append(asyncio.create_task(sentinel_loop(self.stop_event),
                                              name="sentinel"))
        if self.enable.get("secretary"):
            tasks.append(asyncio.create_task(secretary_loop(self.stop_event),
                                              name="secretary"))
        if self.enable.get("creative"):
            tasks.append(asyncio.create_task(creative_loop(self.stop_event),
                                              name="creative"))
        print(f"[swarm] {len(tasks)} workers running: "
              f"{[t.get_name() for t in tasks]}", flush=True)
        write_status("orchestrator", {"status": "running",
                                       "workers": [t.get_name() for t in tasks]})
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            print("[swarm] cancelled", flush=True)
        write_status("orchestrator", {"status": "stopped"})


def main():
    swarm = SwarmOrchestrator()

    def handle_sigint(signum, frame):
        swarm.request_stop()
    signal.signal(signal.SIGINT, handle_sigint)
    try:
        signal.signal(signal.SIGTERM, handle_sigint)
    except Exception:
        pass

    try:
        asyncio.run(swarm.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
