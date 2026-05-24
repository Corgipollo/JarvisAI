"""infinite_ceo.py - El motor de hambre. Bucle 30 min auto-generador.

Despierta cada 30 min, audita estado del negocio, genera SUS PROPIOS
objetivos y los encola via /queue/add. Sin esperar a usuario.

Objetivos legitimos que auto-genera (todos dentro de ToS de plataformas):
  - Research de leads (web publica + DuckDuckGo)
  - Auditoria CRM (leads sin email, leads viejos sin follow-up)
  - Auto-generacion de contenido para posts (Twitter/LinkedIn/HN drafts)
  - Self-improvement runs sobre archivos con TODOs
  - Health check end-to-end del funnel signup
  - Reporte diario consolidado
  - Backup de tenant DBs

NO auto-genera (por razones tecnicas anti-spam reales):
  - DMs masivos en Instagram/Reddit/Twitter (ban garantizado <48h)
  - Compras autonomas con tarjeta del usuario (sin autorizacion por accion)
  - Refactor + auto-push de codigo core sin debate_engine + py_compile pass
  - Override de guardrails CFO/debate ya commiteados

Esos limites no son dogma — son la diferencia entre Sierra ($4.5B) y los
bots que mueren en 6 meses. Documentado en data/reports/agencia_autonoma_live.md
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

API_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:5000")
API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")
CYCLE_MIN = int(os.environ.get("CEO_CYCLE_MIN", "30"))
LOG = ROOT / "data" / "infinite_ceo.log"
REPORT = ROOT / "data" / "reports" / "agencia_autonoma_live.md"
TENANT_DB = ROOT / "data" / "tenants" / "default" / "memory.db"


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _enqueue(objective: str, priority: int = 5, source: str = "infinite_ceo") -> str:
    try:
        r = requests.post(
            f"{API_URL}/queue/add",
            json={"objective": objective, "priority": priority},
            headers={"X-Jarvis-Token": API_TOKEN, "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("qid", "?")
    except Exception as e:
        _log(f"enqueue fail: {e}")
        return ""


def audit_business_state() -> dict:
    """Lee el estado actual del negocio para decidir que tareas generar."""
    state = {
        "leads_total": 0,
        "leads_without_email": 0,
        "leads_sent": 0,
        "leads_replied": 0,
        "leads_pending_followup": 0,
        "tenants_total": 0,
        "tenants_paid": 0,
        "revenue_total_usd": 0.0,
        "queue_pending": 0,
        "queue_failed_24h": 0,
    }
    try:
        if TENANT_DB.exists():
            conn = sqlite3.connect(str(TENANT_DB), timeout=5)
            conn.row_factory = sqlite3.Row
            try:
                # CRM leads
                cur = conn.execute(
                    "SELECT COUNT(*) AS n, "
                    "SUM(CASE WHEN contact_email='' OR contact_email IS NULL THEN 1 ELSE 0 END) AS no_email, "
                    "SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) AS sent, "
                    "SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END) AS replied "
                    "FROM outreach_leads")
                row = cur.fetchone()
                if row:
                    state["leads_total"] = row["n"] or 0
                    state["leads_without_email"] = row["no_email"] or 0
                    state["leads_sent"] = row["sent"] or 0
                    state["leads_replied"] = row["replied"] or 0
                # Pending followup: sent >5 dias sin reply
                cutoff = (datetime.utcnow() - timedelta(days=5)).isoformat()
                cur = conn.execute(
                    "SELECT COUNT(*) FROM outreach_leads "
                    "WHERE status='sent' AND replied=0 AND last_sent_at < ?",
                    (cutoff,))
                state["leads_pending_followup"] = cur.fetchone()[0] or 0
                # Revenue (spend_ledger - cuando facturamos)
                try:
                    cur = conn.execute(
                        "SELECT ROUND(SUM(cost_usd), 4) FROM spend_ledger "
                        "WHERE ts > datetime('now', '-30 days')")
                    state["revenue_total_usd"] = cur.fetchone()[0] or 0.0
                except Exception:
                    pass
            finally:
                conn.close()
        # Tenants count
        tenants_dir = ROOT / "data" / "tenants"
        if tenants_dir.exists():
            tenants = [d for d in tenants_dir.iterdir() if d.is_dir()]
            state["tenants_total"] = len(tenants)
            for t in tenants:
                db = t / "memory.db"
                if not db.exists():
                    continue
                try:
                    c = sqlite3.connect(str(db), timeout=3)
                    cur = c.execute(
                        "SELECT COUNT(*) FROM tenant_meta "
                        "WHERE stripe_subscription_status = 'active'")
                    if cur.fetchone()[0] > 0:
                        state["tenants_paid"] += 1
                    c.close()
                except Exception:
                    pass
        # Queue state via API
        try:
            r = requests.get(
                f"{API_URL}/queue/status",
                headers={"X-Jarvis-Token": API_TOKEN}, timeout=5)
            if r.status_code == 200:
                q = r.json()
                state["queue_pending"] = q.get("pending_count", 0)
        except Exception:
            pass
    except Exception as e:
        _log(f"audit error: {e}")
    return state


def generate_objectives(state: dict) -> list[tuple[str, int]]:
    """Decide que tareas encolar basado en el estado. Retorna lista de
    (objective_text, priority). Tareas legitimas, sin riesgo."""
    objectives: list[tuple[str, int]] = []

    # Objetivo 1: si hay leads sin email, investigar emails publicos
    if state["leads_without_email"] >= 3:
        objectives.append((
            "MODO INVESTIGACION: ejecuta shell 'python -c \"import sys; "
            "sys.path.insert(0, r\\\"C:/Users/Emmanuel/Documents/JarvisAI\\\"); "
            "from jarvis_v2.tools.research_lead_contacts import bulk_research; "
            "import json; print(json.dumps(bulk_research(limit=5), default=str)[:500])\"' "
            "para investigar emails publicos de 5 leads sin contacto.",
            7))

    # Objetivo 2: si hay leads pending followup, generar drafts dry-run
    if state["leads_pending_followup"] > 0:
        objectives.append((
            f"MODO FOLLOWUP: hay {state['leads_pending_followup']} leads "
            "con email enviado hace >5 dias sin respuesta. Ejecuta shell "
            "'curl -X POST http://127.0.0.1:5000/api/v1/outreach/send "
            "-H \"X-Jarvis-Token: jarvis_a8x29kfp3lz7m2qw9bdv\" "
            "-H \"Content-Type: application/json\" "
            "-d \"{\\\"lead_ids\\\":[1,2,3],\\\"template_id\\\":\\\"agro_v1\\\",\\\"dry_run\\\":true}\"' "
            "para generar drafts de follow-up listos para revision humana.",
            5))

    # Objetivo 3: si hay 0 tenants paid pero >0 signups, audit funnel
    if state["tenants_total"] > 0 and state["tenants_paid"] == 0:
        objectives.append((
            "MODO AUDIT: ejecuta shell 'curl -s http://127.0.0.1:5000/api/v1/tenants "
            "-H \"X-Jarvis-Token: jarvis_a8x29kfp3lz7m2qw9bdv\" > "
            "data/reports/tenants_health_$(powershell -c (Get-Date).ToString(\\\"HHmm\\\")).txt' "
            "para snapshot del funnel.",
            4))

    # Objetivo 4: self-improvement cycle (busca TODO/FIXME y aplica fix)
    if random.random() < 0.4:  # 40% chance cada ciclo
        objectives.append((
            "MODO SELF-IMPROVEMENT: ejecuta shell 'python -m "
            "jarvis_v2.skills.self_improvement --strategy todo_or_old "
            "--no-push' para mejora puntual sobre archivo random con TODO. "
            "Sin push automatico - commit local solo.",
            3))

    # Objetivo 5: research de mercado / competencia (siempre algo)
    keywords_pool = [
        "OmniParser update 2026",
        "GUI agent benchmark Screen Spot Pro",
        "Anthropic Computer Use pricing 2026",
        "vertical SaaS agentic LATAM",
        "AutoDS API changes 2026",
        "Shopify multi-tenant best practices",
    ]
    kw = random.choice(keywords_pool)
    objectives.append((
        f"MODO RESEARCH: investiga novedades sobre '{kw}'. "
        "Ejecuta shell 'python -m jarvis_v2.daemons.omniparser_researcher' "
        "para correr un ciclo extra del researcher.",
        3))

    # Objetivo 6: backup tenant DBs (cada 4 ciclos = ~2h)
    cycle_count = int(time.time() / (CYCLE_MIN * 60))
    if cycle_count % 4 == 0:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        objectives.append((
            f"MODO BACKUP: ejecuta shell 'powershell -Command \""
            f"Compress-Archive -Path data/tenants -DestinationPath "
            f"data/backups/tenants_{ts}.zip -Force\"' para backup de "
            "todas las DBs multi-tenant.",
            2))

    return objectives


def write_report(state: dict, generated: list[tuple[str, int]],
                  qids: list[str]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    cycle = int(time.time() / (CYCLE_MIN * 60))
    # Append, no sobreescribe (historial de evolucion)
    header_new = not REPORT.exists()
    with REPORT.open("a", encoding="utf-8") as f:
        if header_new:
            f.write("# Agencia Autonoma — Bitacora del CEO Perpetuo\n\n")
            f.write("> Daemon `infinite_ceo.py` corre cada 30 min auto-generando objetivos.\n")
            f.write("> Cada entrada es un ciclo. Append-only, no sobreescribe.\n\n")
            f.write("**Boundaries respetadas siempre** (decision arquitectonica):\n")
            f.write("- NO genera DMs masivos Reddit/Twitter/Instagram (ban garantizado)\n")
            f.write("- NO compras autonomas con tarjeta del usuario sin OK por accion\n")
            f.write("- NO refactor + push core sin debate_engine + py_compile pass\n")
            f.write("- SI genera: research, audits, drafts dry-run, self-improvement local, backups\n\n")
            f.write("---\n\n")
        f.write(f"## Ciclo #{cycle} — {ts}\n\n")
        f.write("### Estado del negocio\n")
        f.write(f"- Leads total: {state['leads_total']}\n")
        f.write(f"- Leads sin email: {state['leads_without_email']}\n")
        f.write(f"- Leads enviados: {state['leads_sent']}\n")
        f.write(f"- Leads pending followup (>5d): {state['leads_pending_followup']}\n")
        f.write(f"- Tenants total: {state['tenants_total']}\n")
        f.write(f"- Tenants pagados (Stripe active): {state['tenants_paid']}\n")
        f.write(f"- Revenue 30d USD: ${state['revenue_total_usd']:.4f}\n")
        f.write(f"- Queue pending: {state['queue_pending']}\n\n")
        f.write(f"### Objetivos generados ({len(generated)})\n")
        for (obj, prio), qid in zip(generated, qids):
            f.write(f"- [prio {prio}] qid={qid} — {obj[:120]}...\n")
        f.write("\n---\n\n")


def cycle_once() -> None:
    _log(f"=== Ciclo CEO start ===")
    state = audit_business_state()
    _log(f"state: leads={state['leads_total']} paid_tenants={state['tenants_paid']} "
         f"revenue={state['revenue_total_usd']:.4f} queue_pend={state['queue_pending']}")

    # Skip generacion si queue ya tiene mucho (no spamming)
    if state["queue_pending"] >= 10:
        _log(f"queue saturada ({state['queue_pending']} pending), skip generacion")
        write_report(state, [], [])
        return

    objectives = generate_objectives(state)
    _log(f"objetivos generados: {len(objectives)}")
    qids: list[str] = []
    for obj, prio in objectives:
        qid = _enqueue(obj, priority=prio)
        if qid:
            qids.append(qid)
            _log(f"  enqueued qid={qid} prio={prio}: {obj[:80]}")
    write_report(state, objectives, qids)
    _log(f"=== Ciclo CEO end (encoladas {len(qids)}/{len(objectives)}) ===")


def main_loop() -> None:
    _log(f"=== INFINITE CEO started, cycle every {CYCLE_MIN} min ===")
    while True:
        try:
            cycle_once()
        except Exception as e:
            _log(f"cycle EXCEPTION: {e}")
        sleep_s = CYCLE_MIN * 60
        _log(f"sleeping {sleep_s}s hasta siguiente ciclo")
        time.sleep(sleep_s)


if __name__ == "__main__":
    main_loop()
