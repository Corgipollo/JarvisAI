"""sales_trainer.py - Auto-mejora del pitch outreach via debate engine.

Filosofia:
  Jarvis envia cold emails con N templates ya hardcoded (agro_v1, ecommerce_v1,
  agency_v1). Si despues de X envios el reply_rate sigue bajo, NO sirve
  insistir con el mismo pitch — hay que reescribirlo.

  Pero antes de reescribir, hay que tener DATOS suficientes para distinguir
  pitch malo de mala suerte. Sample size matters: con 5 envios, 0 replies
  no significa nada. Con 50 envios y 0 replies, el pitch esta muerto.

Trigger conditions (ALL must be true):
  1. sent_count >= MIN_SAMPLE (default 25)
  2. reply_rate < TARGET_REPLY_RATE (default 0.02 = 2%)
  3. No se disparo training para este template en las ultimas 24h
  4. Han pasado >= 4h desde el ultimo envio con este template
     (si ahorita esta caliente el batch, espera a que termine)

Action cuando trigger:
  1. Lee template actual + stats (sent, opens, clicks, replied)
  2. Lee ultimos 5 inbound responses (positive/negative) si hay
  3. Llama debate_engine.debate() con focus="por que conversion baja"
  4. Si debate produce final_code (=pitch reescrito), guarda como variante
     {template_id}_v{N+1} en TEMPLATES dict EN MEMORIA + persiste a
     data/templates_evolved/{id}.json
  5. Marca en data/sales_trainer_state.json el ts del ultimo training
     y la metrica que detono.

NO modifica TEMPLATES en codigo (no hot-patch al archivo .py). Variantes
nuevas viven en data/templates_evolved/ y el operator humano (Emmanuel)
las puede revisar antes de promoverlas a TEMPLATES oficiales. Decision
explicita: el agente puede PROPONER pero no DESPLEGAR pitches nuevos
sin review humana hasta que tengamos baseline >100 envios validados.

Registro: schtask Jarvis_Sales_Trainer cada 6 horas.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEFAULT_TENANT_DB = ROOT / "data" / "tenants" / "default" / "memory.db"
STATE_FILE = ROOT / "data" / "sales_trainer_state.json"
EVOLVED_DIR = ROOT / "data" / "templates_evolved"

MIN_SAMPLE = int(os.environ.get("SALES_TRAINER_MIN_SAMPLE", "25"))
TARGET_REPLY_RATE = float(os.environ.get("SALES_TRAINER_TARGET_REPLY_RATE", "0.02"))
COOLDOWN_HOURS = int(os.environ.get("SALES_TRAINER_COOLDOWN_HOURS", "24"))
QUIET_HOURS_AFTER_BATCH = int(os.environ.get("SALES_TRAINER_QUIET_HOURS", "4"))


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def _gather_template_stats() -> dict[str, dict]:
    """Por template, calcula: sent, opens, clicks, replied, reply_rate, last_sent_at."""
    if not DEFAULT_TENANT_DB.exists():
        return {}
    conn = sqlite3.connect(str(DEFAULT_TENANT_DB), timeout=5)
    conn.row_factory = sqlite3.Row
    out: dict[str, dict] = {}
    try:
        # outreach_events.metadata stores template_id when event='sent'
        rows = conn.execute("""
            SELECT metadata as template_id, COUNT(*) as sent
            FROM outreach_events
            WHERE event = 'sent'
            GROUP BY metadata
        """).fetchall()
        for r in rows:
            tid = r["template_id"] or "unknown"
            out[tid] = {"sent": int(r["sent"]), "opens": 0, "clicks": 0, "replied": 0}

        # opens/clicks/replied estan al nivel de lead, no de template.
        # Inferimos joining outreach_leads.last_template_used (no existe en schema
        # actual) — workaround: usamos last_template via outreach_events ultimo 'sent'
        # por lead.
        last_tpl_rows = conn.execute("""
            SELECT lead_id, metadata as template_id, MAX(ts) as last_ts
            FROM outreach_events
            WHERE event = 'sent'
            GROUP BY lead_id
        """).fetchall()
        lead_to_tpl = {r["lead_id"]: r["template_id"] for r in last_tpl_rows}

        leads = conn.execute("""
            SELECT id, opens, clicks, replied, last_sent_at
            FROM outreach_leads WHERE status = 'sent'
        """).fetchall()
        for lead in leads:
            tid = lead_to_tpl.get(lead["id"])
            if not tid or tid not in out:
                continue
            out[tid]["opens"] += int(lead["opens"] or 0)
            out[tid]["clicks"] += int(lead["clicks"] or 0)
            out[tid]["replied"] += int(lead["replied"] or 0)
            ts = lead["last_sent_at"]
            if ts and (out[tid].get("last_sent_at") or "") < ts:
                out[tid]["last_sent_at"] = ts

        for tid, s in out.items():
            sent = s["sent"]
            s["reply_rate"] = s["replied"] / sent if sent else 0.0
            s["open_rate"] = s["opens"] / sent if sent else 0.0
            s["click_rate"] = s["clicks"] / sent if sent else 0.0
    finally:
        conn.close()
    return out


def _should_retrain(tid: str, stats: dict, state: dict) -> tuple[bool, str]:
    sent = stats.get("sent", 0)
    if sent < MIN_SAMPLE:
        return False, f"sample {sent} < min {MIN_SAMPLE} (need more data)"
    reply_rate = stats.get("reply_rate", 0.0)
    if reply_rate >= TARGET_REPLY_RATE:
        return False, f"reply_rate {reply_rate:.2%} >= target {TARGET_REPLY_RATE:.2%}"
    last_train = state.get("last_trained_at", {}).get(tid)
    if last_train:
        try:
            ago = datetime.utcnow() - datetime.fromisoformat(last_train)
            if ago < timedelta(hours=COOLDOWN_HOURS):
                return False, f"cooldown: trained {int(ago.total_seconds()/3600)}h ago < {COOLDOWN_HOURS}h"
        except Exception:
            pass
    last_sent = stats.get("last_sent_at")
    if last_sent:
        try:
            sent_ago = datetime.utcnow() - datetime.fromisoformat(last_sent.replace("Z", ""))
            if sent_ago < timedelta(hours=QUIET_HOURS_AFTER_BATCH):
                return False, f"quiet hours: last send {int(sent_ago.total_seconds()/3600)}h ago < {QUIET_HOURS_AFTER_BATCH}h"
        except Exception:
            pass
    return True, f"sent={sent}, reply_rate={reply_rate:.2%} below {TARGET_REPLY_RATE:.2%}"


def _retrain_template(tid: str, current_stats: dict) -> dict:
    """Llama debate_engine para reescribir el pitch. Guarda variante a disco."""
    try:
        from jarvis_v2.api.outreach_routes import TEMPLATES
        from jarvis_v2.core.debate_engine import debate
    except ImportError as e:
        return {"error": f"import_failed: {e}"}

    if tid not in TEMPLATES:
        return {"error": f"template_not_in_TEMPLATES_dict: {tid}"}
    current = TEMPLATES[tid]

    inbound_signals = ""
    try:
        from jarvis_v2.memory.lead_context import recall_similar_to
        negatives = recall_similar_to(
            "respuesta negativa rechazo no interesa unsubscribe",
            lead_id=None, top_k=3, min_similarity=0.3,
        )
        if negatives:
            inbound_signals = "\nRESPUESTAS NEGATIVAS RECIENTES (top 3):\n" + "\n".join(
                f"- {n['doc'][:200]}" for n in negatives
            )
    except Exception:
        pass

    pitch_text = (
        f"SUBJECT: {current['subject']}\n\n"
        f"BODY:\n{current['body_text']}\n\n"
        f"STATS:\n"
        f"  Sent: {current_stats.get('sent', 0)}\n"
        f"  Opens: {current_stats.get('opens', 0)} ({current_stats.get('open_rate', 0):.1%})\n"
        f"  Clicks: {current_stats.get('clicks', 0)} ({current_stats.get('click_rate', 0):.1%})\n"
        f"  Replied: {current_stats.get('replied', 0)} ({current_stats.get('reply_rate', 0):.1%})\n"
        f"{inbound_signals}"
    )

    focus = (
        "El pitch tiene reply_rate por debajo de 2%. "
        "Identifica: 1) si el subject es generico/spam-trigger, 2) si el body "
        "es muy largo o sin proof concreto, 3) si la CTA es debil. "
        "Critic: enumera issues. Proposer: reescribe SUBJECT + BODY siguiendo "
        "Patio Eleven / Jason Bay style: una linea curiosa de subject, body <120 "
        "palabras, proof especifica con numero, CTA pregunta simple."
    )

    result = debate(pitch_text, focus_areas=focus, max_rounds=2)
    out = {
        "template_id": tid,
        "ts": datetime.utcnow().isoformat(),
        "trigger_stats": current_stats,
        "debate_approved": result.get("approved", False),
        "debate_rounds": result.get("rounds", 0),
        "issues_found_count": len(result.get("issues_found", [])),
        "new_pitch": result.get("final_code"),
    }

    if out["new_pitch"]:
        EVOLVED_DIR.mkdir(parents=True, exist_ok=True)
        variant_path = EVOLVED_DIR / f"{tid}_evolved_{datetime.utcnow().strftime('%Y%m%d_%H%M')}.json"
        variant_path.write_text(
            json.dumps({**out, "current_stats": current_stats,
                        "current_pitch": current},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        out["saved_to"] = str(variant_path)
    return out


def cycle_once() -> dict:
    _log("=== Sales Trainer cycle start ===")
    state = _load_state()
    state.setdefault("last_trained_at", {})

    stats_by_tpl = _gather_template_stats()
    _log(f"templates con stats: {list(stats_by_tpl.keys())}")
    if not stats_by_tpl:
        _log("no outreach data yet — skip cycle")
        return {"ok": True, "skipped": "no_data"}

    results = []
    retrained = 0
    for tid, st in stats_by_tpl.items():
        should, reason = _should_retrain(tid, st, state)
        _log(f"  {tid}: should_retrain={should} ({reason})")
        if not should:
            results.append({"template": tid, "skipped": reason, "stats": st})
            continue
        r = _retrain_template(tid, st)
        results.append({"template": tid, "retrained": True, "result": r})
        if r.get("new_pitch"):
            state["last_trained_at"][tid] = datetime.utcnow().isoformat()
            retrained += 1
            _log(f"  -> retrained {tid}; variant saved to {r.get('saved_to')}")
        else:
            _log(f"  -> debate did not produce refactor: {r.get('error') or 'no_final_code'}")

    _save_state(state)
    _log(f"=== Cycle end. Retrained {retrained}/{len(stats_by_tpl)} ===")
    return {"ok": True, "retrained": retrained, "scanned": len(stats_by_tpl), "details": results}


if __name__ == "__main__":
    r = cycle_once()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
