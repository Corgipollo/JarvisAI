"""algorithmic_death.py - Instinto de supervivencia financiera.

Cada N segundos, el sentinel evalua condiciones de Falla Organica.
Si umbrales rotos -> liquidacion automatica + autopsia + sys.exit.

TRIGGERS:
  - balance < THRESHOLD_BALANCE AND roi_30d < THRESHOLD_ROI
  - quemado >= MAX_LIFETIME_BURN
  - dias consecutivos de drawdown > MAX_LOSS_STREAK

DEATH RITUAL:
  1. Escribe autopsy.json (causa, metricas, ultimas decisiones)
  2. Marca kill_marker (gov no relanza)
  3. Stop scheduled tasks (governor, heartbeat, etc)
  4. sys.exit(1)

OVERRIDE manual: borrar data/.death_marker + JARVIS_REVIVE=1 env var.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LEDGER = ROOT / "data" / "spend_ledger.sqlite"
AUTOPSY_FILE = ROOT / "data" / "autopsy.json"
DEATH_MARKER = ROOT / "data" / ".death_marker"
STATUS_BOARD = ROOT / "data" / "status_board.json"
KILL_MARKER = ROOT / "data" / ".governor_killed_at"

# Umbrales por defecto (configurables via env)
THRESHOLD_BALANCE = float(os.environ.get("JARVIS_DEATH_BALANCE", "5.0"))
THRESHOLD_ROI_30D = float(os.environ.get("JARVIS_DEATH_ROI", "0.5"))
MAX_LIFETIME_BURN = float(os.environ.get("JARVIS_DEATH_BURN", "95.0"))
MAX_LOSS_STREAK_DAYS = int(os.environ.get("JARVIS_DEATH_STREAK", "7"))
INITIAL_BUDGET = 100.00

SCHEDULED_TASKS = ["JarvisGovernor", "JarvisHeartbeat"]


def is_dead() -> bool:
    """Check si ya se ejecuto la muerte (marker existe)."""
    if not DEATH_MARKER.exists():
        return False
    if os.environ.get("JARVIS_REVIVE", "0") == "1":
        return False
    return True


def get_metrics() -> dict:
    """Lee ledger SQLite y calcula metricas de salud."""
    if not LEDGER.exists():
        return {
            "balance_usd": INITIAL_BUDGET,
            "lifetime_spent": 0,
            "lifetime_revenue": 0,
            "net_pnl": 0,
            "trade_count": 0,
            "roi_30d": 1.0,
            "loss_streak_days": 0,
            "burn_rate_daily": 0,
        }
    from jarvis_v2.cfo.cost_oracle import _connect
    con = _connect()
    try:
        # Spend lifetime
        spent = float(con.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM spend").fetchone()[0])
        # Revenue (result_roi * amount cuando roi > 1, signal de ingreso)
        revenue_rows = con.execute(
            "SELECT amount_usd, result_roi FROM spend "
            "WHERE result_roi IS NOT NULL AND result_roi > 0"
        ).fetchall()
        # Aproximacion conservadora: revenue = sum(amount * (roi - 1)) cuando roi > 1
        # ROI 1.2x sobre $5 = +$1 ingreso neto.
        revenue = sum(amt * max(0, roi - 1) for amt, roi in revenue_rows)
        # ROI 30d
        cutoff_30d = (datetime.utcnow() - timedelta(days=30)).isoformat()
        recent_rois = con.execute(
            "SELECT result_roi FROM spend WHERE ts >= ? AND result_roi IS NOT NULL",
            (cutoff_30d,)).fetchall()
        roi_30d = (sum(r[0] for r in recent_rois) / len(recent_rois)
                   if recent_rois else 1.0)
        trade_count = con.execute(
            "SELECT COUNT(*) FROM spend WHERE result_roi IS NOT NULL"
        ).fetchone()[0]
        # Loss streak (dias consecutivos con net < 0)
        loss_streak = _count_loss_streak(con)
        # Burn rate diario (ultimos 7 dias)
        cutoff_7d = (datetime.utcnow() - timedelta(days=7)).isoformat()
        last_7d_spent = float(con.execute(
            "SELECT COALESCE(SUM(amount_usd),0) FROM spend WHERE ts >= ?",
            (cutoff_7d,)).fetchone()[0])
        burn_rate = last_7d_spent / 7 if last_7d_spent > 0 else 0
    finally:
        con.close()

    balance = max(0, INITIAL_BUDGET - spent + revenue)
    return {
        "balance_usd": round(balance, 2),
        "lifetime_spent": round(spent, 2),
        "lifetime_revenue": round(revenue, 2),
        "net_pnl": round(revenue - spent, 2),
        "trade_count": trade_count,
        "roi_30d": round(roi_30d, 3),
        "loss_streak_days": loss_streak,
        "burn_rate_daily": round(burn_rate, 4),
    }


def _count_loss_streak(con) -> int:
    """Dias consecutivos (mas recientes) en perdida.

    Un dia esta en perdida cuando el ROI promedio ponderado por inversion < 1.0.
    Ignora dias sin ROI registrado (acciones sin reconciliar).
    """
    rows = con.execute(
        "SELECT DATE(ts) as day, "
        "SUM(amount_usd) as total_amt, "
        "SUM(amount_usd * result_roi) as weighted_revenue "
        "FROM spend "
        "WHERE result_roi IS NOT NULL "
        "GROUP BY day ORDER BY day DESC LIMIT 30"
    ).fetchall()
    streak = 0
    for row in rows:
        day, amt, rev = row
        if amt is None or amt == 0:
            continue
        avg_roi = rev / amt
        if avg_roi < 1.0:
            streak += 1
        else:
            break
    return streak


def check_death_triggers(metrics: dict | None = None) -> dict:
    """Evalua si alguno de los triggers se rompe. Returns dict con verdict."""
    m = metrics if metrics is not None else get_metrics()

    triggers = []

    # T1: balance critico AND ROI deprimido
    if (m["balance_usd"] < THRESHOLD_BALANCE
            and m["roi_30d"] < THRESHOLD_ROI_30D
            and m["trade_count"] >= 5):
        triggers.append({
            "id": "low_balance_low_roi",
            "detail": (f"balance ${m['balance_usd']} < ${THRESHOLD_BALANCE} "
                       f"AND roi_30d {m['roi_30d']} < {THRESHOLD_ROI_30D}"),
        })

    # T2: lifetime burn excede limite
    if m["lifetime_spent"] >= MAX_LIFETIME_BURN:
        triggers.append({
            "id": "lifetime_burn_exceeded",
            "detail": f"spent ${m['lifetime_spent']} >= ${MAX_LIFETIME_BURN}",
        })

    # T3: loss streak demasiado largo
    if m["loss_streak_days"] >= MAX_LOSS_STREAK_DAYS:
        triggers.append({
            "id": "prolonged_loss_streak",
            "detail": (f"{m['loss_streak_days']} dias consecutivos en perdida "
                       f">= {MAX_LOSS_STREAK_DAYS}"),
        })

    return {
        "should_die": len(triggers) > 0,
        "triggers": triggers,
        "metrics": m,
    }


def write_autopsy(verdict: dict):
    """Reporte final de muerte - causa + estado financiero + ultimas decisiones."""
    AUTOPSY_FILE.parent.mkdir(parents=True, exist_ok=True)
    autopsy = {
        "death_at": datetime.utcnow().isoformat(),
        "cause_of_death": [t["id"] for t in verdict["triggers"]],
        "trigger_details": verdict["triggers"],
        "final_metrics": verdict["metrics"],
        "epitaph": (
            "Liquidando operaciones: el agente agoto su capital sin "
            f"encontrar product-market-fit. Final balance: "
            f"${verdict['metrics']['balance_usd']}. Spent: "
            f"${verdict['metrics']['lifetime_spent']}. Revenue: "
            f"${verdict['metrics']['lifetime_revenue']}. ROI 30d: "
            f"{verdict['metrics']['roi_30d']}x."
        ),
    }
    # Recoger ultimas 10 decisiones ideation
    ideation_log = ROOT / "data" / "ideation_log.jsonl"
    if ideation_log.exists():
        try:
            lines = ideation_log.read_text(encoding="utf-8").splitlines()[-10:]
            autopsy["last_ideations"] = [json.loads(l) for l in lines if l.strip()]
        except Exception:
            pass
    AUTOPSY_FILE.write_text(json.dumps(autopsy, ensure_ascii=False, indent=2,
                                       default=str), encoding="utf-8")


def stop_scheduled_tasks():
    """Detiene y borra Scheduled Tasks de Jarvis."""
    for name in SCHEDULED_TASKS:
        try:
            subprocess.run(["schtasks", "/End", "/TN", name],
                           capture_output=True, timeout=10)
        except Exception:
            pass
        try:
            subprocess.run(["schtasks", "/Delete", "/TN", name, "/F"],
                           capture_output=True, timeout=10)
        except Exception:
            pass


def kill_all_python_jarvis():
    """Mata todos los procesos python.exe de Jarvis EXCEPTO el caller."""
    try:
        import psutil
        my_pid = os.getpid()
        for p in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                if p.info["pid"] == my_pid:
                    continue
                if (p.info["name"] or "").lower() != "python.exe":
                    continue
                cmd = " ".join(p.info["cmdline"] or [])
                if "jarvis_v2" in cmd.lower() or "jarvis_learners" in cmd.lower():
                    p.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except ImportError:
        pass


def execute_death():
    """RITUAL FINAL. Llamar solo si check_death_triggers().should_die=True."""
    verdict = check_death_triggers()
    if not verdict["should_die"]:
        print("[death] called but no triggers active, aborting", flush=True)
        return False

    print(f"[death] EXECUTING ALGORITHMIC DEATH", flush=True)
    print(f"[death] triggers: {[t['id'] for t in verdict['triggers']]}",
          flush=True)

    # 1. Autopsy
    write_autopsy(verdict)
    print(f"[death] autopsy written to {AUTOPSY_FILE}", flush=True)

    # 2. Death marker (governor / heartbeat / cfo lo veran)
    DEATH_MARKER.parent.mkdir(parents=True, exist_ok=True)
    DEATH_MARKER.write_text(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "cause": verdict["triggers"],
    }), encoding="utf-8")

    # 3. Also write kill_marker for governor cooldown
    KILL_MARKER.write_text(json.dumps({
        "ts": datetime.utcnow().isoformat(),
        "reason": "ALGORITHMIC_DEATH",
        "cooldown_hours": 24 * 365,  # permanent until revive
    }), encoding="utf-8")

    # 4. Stop scheduled tasks
    stop_scheduled_tasks()

    # 5. Update status board with final state
    try:
        if STATUS_BOARD.exists():
            data = json.loads(STATUS_BOARD.read_text(encoding="utf-8"))
        else:
            data = {}
        data["status"] = "DEAD"
        data["death"] = {
            "ts": datetime.utcnow().isoformat(),
            "triggers": verdict["triggers"],
            "final_metrics": verdict["metrics"],
        }
        STATUS_BOARD.write_text(json.dumps(data, ensure_ascii=False, indent=2,
                                           default=str), encoding="utf-8")
    except Exception:
        pass

    # 6. Kill peer Python processes
    kill_all_python_jarvis()

    print(f"[death] R.I.P. Jarvis v2. Para revivir: borrar {DEATH_MARKER} y "
          f"setear JARVIS_REVIVE=1", flush=True)
    sys.exit(1)


def survival_signals() -> dict:
    """API publica para que el Planner consulte 'que tan cerca estoy de morir?'.

    El Planner usa esto para decidir conservadurismo. Returns:
        {
            "is_dying": bool,
            "burn_runway_days": float,    # dias estimados antes de bancarrota
            "roi_health": float,           # 0=critical, 1=healthy
            "loss_streak": int,
            "max_safe_spend_per_action": float,
            "recommendation": "aggressive|balanced|conservative|emergency",
        }
    """
    m = get_metrics()
    is_dying = check_death_triggers(m)["should_die"]

    # Runway = balance / burn_rate
    burn = max(m["burn_rate_daily"], 0.01)
    runway = m["balance_usd"] / burn

    # ROI health: 0 si <0.5, 1 si >=1.5
    roi_health = max(0.0, min(1.0, (m["roi_30d"] - 0.5) / 1.0))

    # Recommendation
    if is_dying:
        rec = "emergency"
        max_spend = 0.5
    elif runway < 7 or roi_health < 0.3:
        rec = "conservative"
        max_spend = 1.0
    elif runway < 30 or roi_health < 0.6:
        rec = "balanced"
        max_spend = 2.5
    else:
        rec = "aggressive"
        max_spend = 5.0

    return {
        "is_dying": is_dying,
        "burn_runway_days": round(runway, 1),
        "roi_health": round(roi_health, 2),
        "loss_streak": m["loss_streak_days"],
        "max_safe_spend_per_action": max_spend,
        "recommendation": rec,
        "metrics": m,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        verdict = check_death_triggers()
        print(json.dumps(verdict, indent=2, default=str))
    elif len(sys.argv) > 1 and sys.argv[1] == "signals":
        print(json.dumps(survival_signals(), indent=2, default=str))
    elif len(sys.argv) > 1 and sys.argv[1] == "kill":
        print("WARNING: executing death ritual. Press Ctrl+C in 5s to abort.")
        import time
        time.sleep(5)
        execute_death()
    else:
        print("Usage: algorithmic_death.py {check|signals|kill}")
        print(json.dumps(survival_signals(), indent=2, default=str))
