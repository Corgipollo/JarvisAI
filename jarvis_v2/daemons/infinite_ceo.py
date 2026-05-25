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
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

API_URL = os.environ.get("JARVIS_API_URL", "http://127.0.0.1:5000")
API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")
CYCLE_MIN = int(os.environ.get("CEO_CYCLE_MIN", "30"))
# CEO_CYCLE_SEC override (en segundos). Si se setea, gana sobre CYCLE_MIN.
# Util para modo "always-on" agresivo. La guardia queue_pending>=10 dentro de
# cycle_once() evita explosion: si la cola se satura, skip silenciosamente.
CYCLE_SEC = int(os.environ.get("CEO_CYCLE_SEC", str(CYCLE_MIN * 60)))
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
            json={
                "objective": objective,
                "priority": priority,
                "source": source,
            },
            headers={"X-Jarvis-Token": API_TOKEN, "Content-Type": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("qid", "?")
    except requests.exceptions.Timeout:
        _log(f"enqueue timeout (source={source}): request exceeded 10s")
        return ""
    except requests.exceptions.ConnectionError as e:
        _log(f"enqueue connection error (source={source}): {e}")
        return ""
    except requests.exceptions.HTTPError as e:
        _log(f"enqueue http error (source={source}): {e.response.status_code}")
        return ""
    except Exception as e:
        _log(f"enqueue fail (source={source}): {e}")
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


def _objective_research_leads() -> tuple[str, int]:
    """Research emails publicos via shell script tangible.

    Antes generaba objetivo natural-language que el planner skipeaba por
    duplicate_recent sin producir output. Ahora invoca shell -> script
    standalone que SIEMPRE escribe un .md con datos reales.
    """
    return (
        "Ejecuta este comando shell exacto sin modificarlo: "
        "python C:/Users/Emmanuel/Documents/JarvisAI/scripts/lead_research_writer.py",
        7
    )


def _objective_followup_leads(pending_count: int) -> tuple[str, int]:
    """Generar followups dry-run usando POST /api/v1/outreach/send con dry_run=true."""
    return (
        f"Hay {pending_count} leads con email enviado >5 dias sin reply. "
        f"Usa GET /api/v1/outreach/leads para listarlos (filtra status='sent' replied=0), "
        f"luego POST /api/v1/outreach/send con dry_run=true y un template followup_v1 "
        f"para previsualizar drafts sin enviar.",
        5
    )


def _objective_audit_funnel(tenants_total: int) -> tuple[str, int]:
    """Audit funnel via shell script tangible (siempre escribe .md)."""
    return (
        "Ejecuta este comando shell exacto sin modificarlo: "
        "python C:/Users/Emmanuel/Documents/JarvisAI/scripts/audit_funnel_writer.py",
        4
    )


def _objective_self_improvement() -> tuple[str, int]:
    """Self-improvement via /execute (interpreta instruccion + corre skills)."""
    return (
        "Self-improvement: escanea jarvis_v2/ buscando TODO/FIXME/XXX comments "
        "en archivos modificados ultimos 7 dias. Selecciona uno con severidad alta "
        "y propone fix concreto (no aplica al codigo). Reporta a data/reports/todo_review.md.",
        3
    )


def _objective_market_research(keyword: str) -> tuple[str, int]:
    """Market research via shell script tangible (rota topics, escribe .md timestamped)."""
    # El script rota topics internamente. Si quieres keyword especifico, lo pasa
    # como arg quoted; sino script elige 3 del pool default.
    if keyword and len(keyword) < 80:
        kw_safe = keyword.replace('"', '').replace("'", "")[:60]
        return (
            f"Ejecuta este comando shell exacto sin modificarlo: "
            f'python C:/Users/Emmanuel/Documents/JarvisAI/scripts/competitor_research_writer.py "{kw_safe}"',
            3
        )
    return (
        "Ejecuta este comando shell exacto sin modificarlo: "
        "python C:/Users/Emmanuel/Documents/JarvisAI/scripts/competitor_research_writer.py",
        3
    )


def _objective_backup_tenants(timestamp: str) -> tuple[str, int]:
    """Backup via /execute con shell command (no endpoint backup falso)."""
    return (
        f"Backup: comprime con shutil.make_archive() las DBs de data/tenants/*/memory.db "
        f"a data/backups/tenants_{timestamp}.zip. Mantiene ultimas 7 copias.",
        2
    )


def generate_objectives(state: dict) -> list[tuple[str, int]]:
    """Decide que tareas encolar basado en el estado. Retorna lista de
    (objective_text, priority). Tareas legitimas, via API endpoints seguros."""
    objectives: list[tuple[str, int]] = []

    # Objetivo 1: si hay leads sin email, investigar emails publicos
    if state["leads_without_email"] >= 3:
        objectives.append(_objective_research_leads())

    # Objetivo 2: si hay leads pending followup, generar drafts dry-run
    if state["leads_pending_followup"] > 0:
        objectives.append(_objective_followup_leads(state["leads_pending_followup"]))

    # Objetivo 3: si hay 0 tenants paid pero >0 signups, audit funnel
    if state["tenants_total"] > 0 and state["tenants_paid"] == 0:
        objectives.append(_objective_audit_funnel(state["tenants_total"]))

    # Objetivo 4: self-improvement cycle (busca TODO/FIXME y aplica fix)
    if random.random() < 0.4:  # 40% chance cada ciclo
        objectives.append(_objective_self_improvement())

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
    objectives.append(_objective_market_research(kw))

    # Objetivo 6: backup tenant DBs (cada 4 ciclos = ~2h)
    cycle_count = int(time.time() / (CYCLE_MIN * 60))
    if cycle_count % 4 == 0:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
        objectives.append(_objective_backup_tenants(ts))

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
            f.write("**Boundaries respetados siempre** (decision arquitectonica):\n")
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

    # Filtrar objetivos que ya han fallado N veces consecutivas (memoria)
    try:
        from jarvis_v2.memory import task_failure_memory
        filtered = []
        skipped = 0
        for obj, prio in objectives:
            should, reason = task_failure_memory.should_skip(obj, threshold=3)
            if should:
                skipped += 1
                _log(f"  SKIP por memoria de fallos: {obj[:60]}... ({reason})")
                continue
            filtered.append((obj, prio))
        objectives = filtered
        if skipped:
            _log(f"  filtrados {skipped} objetivos por memoria")
    except Exception as e:
        _log(f"  failure_memory check fallo (no fatal): {e}")

    qids: list[str] = []
    for obj, prio in objectives:
        qid = _enqueue(obj, priority=prio)
        if qid:
            qids.append(qid)
            _log(f"  enqueued qid={qid} prio={prio}: {obj[:80]}")
    write_report(state, objectives, qids)
    _log(f"=== Ciclo CEO end (encoladas {len(qids)}/{len(objectives)}) ===")


def main_loop() -> None:
    _log(f"=== INFINITE CEO started, cycle every {CYCLE_SEC}s ===")
    # Si intervalo agresivo (<60s), no logear el sleep cada ciclo (spam log)
    silent_sleep = CYCLE_SEC < 60
    while True:
        try:
            cycle_once()
        except Exception as e:
            _log(f"cycle EXCEPTION: {e}")
        if not silent_sleep:
            _log(f"sleeping {CYCLE_SEC}s hasta siguiente ciclo")
        time.sleep(CYCLE_SEC)


if __name__ == "__main__":
    main_loop()
