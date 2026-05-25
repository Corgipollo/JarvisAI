"""task_worker.py - Daemon que NUNCA para. Procesa queue infinita.

Loop:
  1. Si hay task pending en queue -> POST /execute -> esperar -> marcar done/failed
  2. Si queue vacia -> dispara ideation_engine para llenar 3-5 tareas nuevas
  3. Sleep corto + loop

Pensado para 24/7. Costo bajo con Haiku como cerebro default (router dinamico).
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_v2 import task_queue as Q

API_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:5000")
API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")
POLL_INTERVAL = int(os.environ.get("WORKER_POLL_SEC", "20"))
TASK_TIMEOUT = int(os.environ.get("WORKER_TASK_TIMEOUT_SEC", "600"))
IDLE_REFILL_AFTER = int(os.environ.get("WORKER_IDLE_REFILL_MIN", "5"))
MIN_QUEUE_TARGET = int(os.environ.get("WORKER_MIN_QUEUE", "3"))

_HEADERS = {"X-Jarvis-Token": API_TOKEN, "Content-Type": "application/json"}
WORKER_LOG = ROOT / "data" / "task_worker.log"


def log(msg: str):
    line = f"[worker {datetime.utcnow().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        WORKER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with WORKER_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def dispatch_task(item: dict) -> dict:
    """POST /execute y poll hasta terminal status."""
    try:
        r = requests.post(f"{API_URL}/execute",
                          json={"objective": item["objective"],
                                 "priority": item.get("priority", 5)},
                          headers=_HEADERS, timeout=30)
        r.raise_for_status()
        task_id = r.json().get("task_id", "")
        log(f"  dispatched {item['qid']} -> task_id={task_id}")
    except Exception as e:
        return {"ok": False, "error": f"dispatch_fail: {e}"}

    # Poll
    started = time.time()
    while time.time() - started < TASK_TIMEOUT:
        time.sleep(POLL_INTERVAL)
        try:
            t = requests.get(f"{API_URL}/tasks/{task_id}",
                              headers=_HEADERS, timeout=10).json()
            if t.get("status") not in ("queued", "running"):
                return {"ok": True, "task_id": task_id,
                        "status": t.get("status"),
                        "error": t.get("error", "")}
        except Exception as e:
            log(f"  poll error: {e}")
    return {"ok": False, "task_id": task_id, "error": "task_timeout"}


def refill_queue_via_ideation() -> int:
    """Pide a ideation_engine que sugiera N tareas nuevas y las encola."""
    try:
        from jarvis_v2.core.ideation_engine import propose_topics
        topics = propose_topics(limit=MIN_QUEUE_TARGET)
    except Exception as e:
        # Fallback: agregar tareas seed conocidas
        log(f"  ideation_engine fallo: {e} -> usando seeds default")
        topics = [
            "Lee el archivo data/task_worker.log y resume errores recientes en data/health_report.md",
            "Lista archivos en C:/Jarvis/workspace/ y reporta tamanos a data/workspace_report.md",
            "Genera idea de mejora para jarvis_v2/skills/youtube_watcher.py y guarda en data/ideas/yt_watcher.md",
        ]
    n = 0
    for t in topics[:MIN_QUEUE_TARGET]:
        if isinstance(t, dict):
            text = t.get("objective") or t.get("topic") or str(t)
        else:
            text = str(t)
        if not text or len(text) < 10:
            continue
        Q.add(text, priority=3, source="autonomous_refill",
              tags=["auto", "refill"])
        n += 1
    return n


CONSECUTIVE_FAIL_PAUSE = int(os.environ.get("WORKER_FAIL_PAUSE_MIN", "30"))
MAX_CONSECUTIVE_FAILS = int(os.environ.get("WORKER_MAX_FAILS", "3"))


def main_loop():
    log(f"=== task_worker started ===")
    log(f"  API: {API_URL}")
    log(f"  poll: {POLL_INTERVAL}s timeout: {TASK_TIMEOUT}s")
    log(f"  refill if idle {IDLE_REFILL_AFTER}min, target queue >= {MIN_QUEUE_TARGET}")
    log(f"  circuit breaker: pausa {CONSECUTIVE_FAIL_PAUSE}min tras {MAX_CONSECUTIVE_FAILS} fails consecutivos")

    last_action = time.time()
    consecutive_fails = 0
    while True:
        try:
            item = Q.pop_next()
            if item is None:
                idle_min = (time.time() - last_action) / 60
                if idle_min >= IDLE_REFILL_AFTER:
                    log(f"queue idle {idle_min:.1f}min -> refill")
                    added = refill_queue_via_ideation()
                    log(f"  refilled +{added} tareas")
                    last_action = time.time()
                else:
                    log(f"queue empty, idle {idle_min:.1f}min (refill at {IDLE_REFILL_AFTER}min)")
                time.sleep(POLL_INTERVAL)
                continue

            log(f"work on {item['qid']}: {item['objective'][:80]}")

            # Memoria de fallos: skip si ya fallo >=5 veces consecutivas
            try:
                from jarvis_v2.memory import task_failure_memory as _tfm
                should, reason = _tfm.should_skip(item["objective"], threshold=5)
                if should:
                    log(f"  SKIP qid={item['qid']} (memoria fallos): {reason[:120]}")
                    Q.mark_failed(item["qid"], f"skipped_by_failure_memory: {reason}")
                    continue
            except Exception:
                pass

            result = dispatch_task(item)
            if result.get("ok"):
                Q.mark_done(item["qid"],
                            task_id=result.get("task_id", ""),
                            result={"status": result.get("status"),
                                    "error": result.get("error", "")})
                log(f"  done qid={item['qid']} status={result.get('status')}")
                # Registrar success/failure en memoria persistente
                try:
                    from jarvis_v2.memory import task_failure_memory as _tfm
                    if result.get("status") == "done":
                        _tfm.record_success(item["objective"])
                    else:
                        _tfm.record_failure(
                            objective=item["objective"],
                            error_msg=result.get("error", "") or f"status={result.get('status')}",
                            hint="ver endpoints REALES en task_failure_memory.KNOWN_ENDPOINTS",
                        )
                except Exception:
                    pass
                # Reset circuit breaker en done
                if result.get("status") == "done":
                    consecutive_fails = 0
                else:
                    # status=error pero dispatch OK -> cuenta como fail para CB
                    err = (result.get("error") or "").lower()
                    if "402" in err or "429" in err or "payment" in err or "quota" in err:
                        consecutive_fails += 1
                # Notify Telegram si configurado y task de fuente user (no auto-refill)
                if item.get("source") == "user":
                    try:
                        from jarvis_v2.bridges.telegram_notify import notify, configured
                        if configured():
                            notify(f"Done {item['qid']}: "
                                    f"{item['objective'][:120]}\n"
                                    f"status={result.get('status')}")
                    except Exception:
                        pass
            else:
                Q.mark_failed(item["qid"], result.get("error", "?"))
                log(f"  FAIL qid={item['qid']} {result.get('error', '?')[:120]}")
                # Registrar failure en memoria persistente (dispatch fail)
                try:
                    from jarvis_v2.memory import task_failure_memory as _tfm
                    _tfm.record_failure(
                        objective=item["objective"],
                        error_msg=result.get("error", "dispatch_failed"),
                        hint="dispatch fail; revisa que el endpoint/skill existe",
                    )
                except Exception:
                    pass
                consecutive_fails += 1
                # Circuit breaker: si demasiados fails seguidos, pausa larga
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    log(f"  CIRCUIT BREAKER: {consecutive_fails} fails consecutivos -> "
                        f"pausa {CONSECUTIVE_FAIL_PAUSE}min para no quemar saldo")
                    try:
                        from jarvis_v2.bridges.telegram_notify import notify, configured
                        if configured():
                            notify(f"⚠️ Jarvis CIRCUIT BREAKER: {consecutive_fails} "
                                    f"fails consecutivos. Pausa {CONSECUTIVE_FAIL_PAUSE}min. "
                                    f"Revisar saldo OpenRouter y quotas.")
                    except Exception:
                        pass
                    time.sleep(CONSECUTIVE_FAIL_PAUSE * 60)
                    consecutive_fails = 0
                if item.get("source") == "user":
                    try:
                        from jarvis_v2.bridges.telegram_notify import notify, configured
                        if configured():
                            notify(f"FAIL {item['qid']}: {result.get('error','?')[:200]}")
                    except Exception:
                        pass
            last_action = time.time()
        except KeyboardInterrupt:
            log("ciao")
            break
        except Exception as e:
            log(f"loop error: {type(e).__name__}: {e}")
            traceback.print_exc(file=sys.stderr)
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main_loop()
