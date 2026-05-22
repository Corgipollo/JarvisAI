"""reconciler.py - Post-execution reconciliation.

Despues de ejecutar un trade/API call real, el costo real (slippage+fees)
puede diferir del estimado. Reconciler actualiza el ledger y genera insight
si el Planner subestimo consistentemente.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "data" / "spend_ledger.sqlite"
INSIGHTS = ROOT / "data" / "planner_insights.jsonl"


def reconcile(idem_key: str, actual_cost_usd: float, result_roi: float | None = None,
              notes: str = "") -> dict:
    """Actualiza el ledger con costo real post-execution."""
    if not LEDGER.exists():
        return {"ok": False, "error": "no_ledger"}
    from jarvis_v2.cfo.cost_oracle import _connect
    con = _connect()
    row = con.execute(
        "SELECT id, amount_usd, action_type FROM spend WHERE idempotency_key=?",
        (idem_key,),
    ).fetchone()
    if not row:
        con.close()
        return {"ok": False, "error": "idem_key_not_found"}
    row_id, estimated, action_type = row
    delta = actual_cost_usd - estimated
    con.execute(
        "UPDATE spend SET amount_usd=?, result_roi=?, notes=COALESCE(notes,'')||? "
        "WHERE id=?",
        (actual_cost_usd, result_roi, f"\nRECONCILED delta={delta:+.4f} {notes}",
         row_id),
    )
    con.commit()
    con.close()

    # Si el LLM subestimo significativamente, log insight para que la oracle aprenda
    if delta > 0.50:
        _write_insight(action_type, estimated, actual_cost_usd, delta)

    return {
        "ok": True, "delta": delta, "estimated": estimated,
        "actual": actual_cost_usd, "result_roi": result_roi,
    }


def _write_insight(action_type: str, estimated: float, actual: float, delta: float):
    import json
    INSIGHTS.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.utcnow().isoformat(),
        "action_type": action_type,
        "estimated_usd": estimated,
        "actual_usd": actual,
        "delta_usd": delta,
        "insight": f"Planner underestimated {action_type} by ${delta:.2f}. "
                   f"Oracle should use historical avg.",
    }
    with INSIGHTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        idem = sys.argv[1]
        actual = float(sys.argv[2])
        roi = float(sys.argv[3]) if len(sys.argv) > 3 else None
        print(reconcile(idem, actual, roi))
    else:
        print("Usage: reconciler.py <idem_key> <actual_cost_usd> [result_roi]")
