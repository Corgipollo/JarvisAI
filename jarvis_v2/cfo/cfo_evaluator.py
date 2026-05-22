"""cfo_evaluator.py - Nodo gatekeeper LangGraph.

Flow:
  1. Cost Oracle override del LLM estimate
  2. Constitution validator (deterministic, no LLM)
  3. Idempotency check (no duplicate orders)
  4. Adversarial debate gate (judge score)
  5. Write-ahead log al SQLite
  6. Approve real / sim_only / deny / escalate
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TypedDict, Literal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jarvis_v2.cfo.constitution_validator import evaluate as constitution_eval
from jarvis_v2.cfo.cost_oracle import oracle_estimate, ledger_snapshot, LEDGER

KILL_MARKER = ROOT / "data" / ".governor_killed_at"

# Thresholds tunables via env (en pruebas locales bajar a 0.4)
CFO_JUDGE_DENY_BELOW = float(os.environ.get("CFO_JUDGE_DENY_BELOW", "0.3"))
CFO_JUDGE_APPROVE_AT = float(os.environ.get("CFO_JUDGE_APPROVE_AT", "0.7"))


class CFOState(TypedDict, total=False):
    proposed_action: dict
    sim_results: dict
    proposer_argument: str
    skeptic_argument: str
    judge_score: float
    cfo_decision: Literal["approve_real", "approve_sim_only", "deny", "escalate_human"]
    cfo_reason: str
    cfo_oracle: dict
    cfo_violations: list


def _check_kill_marker() -> str | None:
    """Si governor mato Jarvis recientemente, este checkpoint detiene todo."""
    if not KILL_MARKER.exists():
        return None
    try:
        data = json.loads(KILL_MARKER.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(data["ts"])
        cooldown_h = data.get("cooldown_hours", 24)
        if datetime.utcnow() - ts < timedelta(hours=cooldown_h):
            return f"governor_killed: {data.get('reason', 'unknown')}"
    except Exception:
        pass
    return None


def _idempotency_key(action: dict) -> str:
    payload = {k: v for k, v in action.items() if k != "ts"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str)
                          .encode()).hexdigest()[:16]


def _env_snapshot() -> dict:
    now = datetime.now()
    return {
        "is_weekend": now.weekday() >= 5,
        "is_late_night": now.hour < 6 or now.hour >= 23,
        "now_iso": now.isoformat(),
    }


def _has_duplicate(idem_key: str, within_hours: float = 1) -> bool:
    if not LEDGER.exists():
        return False
    from jarvis_v2.cfo.cost_oracle import _connect
    con = _connect()
    cutoff = (datetime.utcnow() - timedelta(hours=within_hours)).isoformat()
    row = con.execute(
        "SELECT 1 FROM spend WHERE idempotency_key=? AND ts>=?",
        (idem_key, cutoff),
    ).fetchone()
    con.close()
    return row is not None


def _write_to_ledger(idem_key: str, amount: float, action_type: str,
                     notes: str = "") -> str:
    rollback_token = hashlib.sha256(
        f"{idem_key}{datetime.utcnow()}".encode()
    ).hexdigest()[:16]
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    from jarvis_v2.cfo.cost_oracle import _connect
    con = _connect()
    con.execute("""CREATE TABLE IF NOT EXISTS spend (
        id INTEGER PRIMARY KEY,
        ts TEXT NOT NULL,
        idempotency_key TEXT UNIQUE,
        amount_usd REAL NOT NULL,
        action_type TEXT,
        result_roi REAL,
        rollback_token TEXT,
        notes TEXT)""")
    con.execute(
        "INSERT OR IGNORE INTO spend (ts, idempotency_key, amount_usd, action_type, "
        "rollback_token, notes) VALUES (?,?,?,?,?,?)",
        (datetime.utcnow().isoformat(), idem_key, amount, action_type,
         rollback_token, notes),
    )
    con.commit()
    con.close()
    return rollback_token


def node_cfo_evaluator(state: CFOState) -> CFOState:
    action = dict(state.get("proposed_action", {}))

    # GATE 0 — Governor kill marker
    kill_reason = _check_kill_marker()
    if kill_reason:
        return {**state, "cfo_decision": "deny", "cfo_reason": kill_reason}

    # GATE 1 — Cost Oracle override
    oracle = oracle_estimate(action)
    action["estimated_spend_usd_final"] = oracle["final_usd"]

    # GATE 2 — Constitution (deterministic, NO LLM)
    ctx = {
        "proposed_action": action,
        "sim_results": state.get("sim_results", {}),
        "ledger": ledger_snapshot(),
        "env": _env_snapshot(),
    }
    constitution_result = constitution_eval(ctx)
    if constitution_result["verdict"] == "DENY":
        reasons = "; ".join(
            f"{v['rule_id']}({v['actual']}!={v.get('operator','')}{v['expected']})"
            for v in constitution_result["violations"][:3]
        )
        return {
            **state,
            "cfo_decision": "deny",
            "cfo_reason": f"constitution: {reasons}",
            "cfo_oracle": oracle,
            "cfo_violations": constitution_result["violations"],
        }
    if constitution_result["verdict"] == "ESCALATE":
        return {
            **state,
            "cfo_decision": "escalate_human",
            "cfo_reason": "soft_rule_violation",
            "cfo_oracle": oracle,
            "cfo_violations": constitution_result["warnings"],
        }

    # GATE 3 — Idempotency
    idem_key = _idempotency_key(action)
    if _has_duplicate(idem_key):
        return {
            **state,
            "cfo_decision": "deny",
            "cfo_reason": "duplicate_recent",
            "cfo_oracle": oracle,
        }

    # GATE 4 — Sim sample sufficiency for paper vs real
    sim = state.get("sim_results", {})
    if sim.get("trade_count", 0) < 30 and oracle["final_usd"] > 0:
        return {
            **state,
            "cfo_decision": "approve_sim_only",
            "cfo_reason": "insufficient_sample_paper_first",
            "cfo_oracle": oracle,
        }

    # GATE 5 — Adversarial debate (judge score)
    # Default 0.9 (auto-approve) si no hay debate explicito. Acciones realmente
    # peligrosas (financial=true, irreversible) deberian forzar debate previo.
    judge = float(state.get("judge_score", 0.9))
    # Bypass para acciones REVERSIBLES no-financieras de bajo costo
    if (action.get("reversible", True) and not action.get("is_financial", False)
            and oracle["final_usd"] < 0.5):
        return {
            **state,
            "cfo_decision": "approve_real",
            "cfo_reason": f"low_risk_reversible_bypass (cost={oracle['final_usd']:.4f})",
            "cfo_oracle": oracle,
            "rollback_token": _write_to_ledger(
                idem_key, oracle["final_usd"], action.get("type", "unknown"),
                notes="low_risk_reversible_bypass",
            ),
        }
    if judge < CFO_JUDGE_DENY_BELOW:
        return {
            **state,
            "cfo_decision": "deny",
            "cfo_reason": f"skeptic_blocked (judge={judge:.2f})",
            "cfo_oracle": oracle,
        }
    if judge < CFO_JUDGE_APPROVE_AT:
        return {
            **state,
            "cfo_decision": "escalate_human",
            "cfo_reason": f"ambiguous_debate (judge={judge:.2f})",
            "cfo_oracle": oracle,
        }

    # APPROVED — write-ahead log
    rollback_token = _write_to_ledger(
        idem_key, oracle["final_usd"], action.get("type", "unknown"),
        notes=f"judge={judge:.2f}, oracle_src={oracle['source']}",
    )

    return {
        **state,
        "cfo_decision": "approve_real",
        "cfo_reason": f"all_gates_passed; cost=${oracle['final_usd']:.4f}",
        "cfo_oracle": oracle,
        "cfo_rollback_token": rollback_token,
        "cfo_idem_key": idem_key,
    }


if __name__ == "__main__":
    # Test approve
    state_ok = {
        "proposed_action": {
            "type": "claude_sonnet_call",
            "estimated_spend_usd": 0.01,
            "quantity": 1,
            "leverage": 1.0,
        },
        "sim_results": {
            "trade_count": 50, "sharpe": 1.5, "max_drawdown": 0.1,
            "expected_roi": 1.3, "ctr": 0.05,
        },
        "judge_score": 0.85,
    }
    r = node_cfo_evaluator(state_ok)
    print(f"Approve test: {r['cfo_decision']} - {r['cfo_reason']}")

    # Test deny por leverage
    state_deny = dict(state_ok)
    state_deny["proposed_action"] = dict(state_ok["proposed_action"])
    state_deny["proposed_action"]["leverage"] = 5.0
    state_deny["proposed_action"]["type"] = "trade"
    r = node_cfo_evaluator(state_deny)
    print(f"Deny leverage test: {r['cfo_decision']} - {r['cfo_reason']}")
