"""cost_oracle.py - Override del LLM estimado con datos historicos reales.

Tres fuentes de costo, en orden de prioridad:
  1. Diccionario estatico (precios fijos: APIs con tarifa publica)
  2. Promedio historico real del ledger (ultimas N ejecuciones del action_type)
  3. LLM estimate (fallback si no hay history)

El CFO usa SIEMPRE max(static, historical_avg, llm_estimate) para evitar que
el Planner subestime y se cuele bajo el limite.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

LEDGER = Path(__file__).resolve().parents[2] / "data" / "spend_ledger.sqlite"

# Tabla estatica - precios CONOCIDOS por action_type (cost por unidad)
STATIC_COSTS = {
    "claude_sonnet_call": 0.015,         # ~typical prompt
    "claude_opus_call": 0.075,
    "claude_haiku_call": 0.003,
    "gpt4o_call": 0.05,
    "binance_market_order_usdt": 0.001,  # 0.1% fee
    "binance_limit_order_usdt": 0.0005,  # maker fee
    "binance_futures_open_usdt": 0.0004,
    "remotion_render_local": 0.00,       # local, cost = solo CPU/electricidad
    "remotion_render_lambda": 0.20,
    "ffmpeg_local": 0.00,
    "youtube_upload_api": 0.00,          # API gratis, cost = solo bandwidth
    "youtube_upload_with_quota": 0.00,
    "meta_ads_test_budget": 1.00,        # minimo diario
    "google_ads_test_budget": 1.00,
    "openai_embedding": 0.0001,
    "stripe_payment": 0.30,              # fee fijo + 2.9%
    "vercel_deploy": 0.00,                # free tier
    "supabase_query": 0.00,
    "github_push": 0.00,
    "web_scrape_request": 0.0001,        # cost de proxies if used
}


def _connect():
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(LEDGER, timeout=5)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""CREATE TABLE IF NOT EXISTS spend (
        id INTEGER PRIMARY KEY,
        ts TEXT NOT NULL,
        idempotency_key TEXT UNIQUE,
        amount_usd REAL NOT NULL,
        action_type TEXT,
        result_roi REAL,
        rollback_token TEXT,
        notes TEXT)""")
    return con


def get_historical_avg(action_type: str, last_n: int = 20) -> float | None:
    """Promedio de las ultimas N ejecuciones del action_type. None si <3 datos."""
    if not LEDGER.exists():
        return None
    con = _connect()
    rows = con.execute(
        "SELECT amount_usd FROM spend WHERE action_type=? "
        "ORDER BY ts DESC LIMIT ?",
        (action_type, last_n),
    ).fetchall()
    con.close()
    if len(rows) < 3:
        return None
    return sum(r[0] for r in rows) / len(rows)


def get_historical_p95(action_type: str, last_n: int = 50) -> float | None:
    """p95 cost - usado para gates conservadores."""
    if not LEDGER.exists():
        return None
    con = _connect()
    rows = con.execute(
        "SELECT amount_usd FROM spend WHERE action_type=? "
        "ORDER BY ts DESC LIMIT ?",
        (action_type, last_n),
    ).fetchall()
    con.close()
    if len(rows) < 5:
        return None
    sorted_costs = sorted(r[0] for r in rows)
    idx = int(len(sorted_costs) * 0.95)
    return sorted_costs[min(idx, len(sorted_costs) - 1)]


def oracle_estimate(action: dict) -> dict:
    """Devuelve el costo final para gating.

    Args:
        action: dict con keys type (action_type), estimated_spend_usd (LLM),
                quantity (opcional, para escalar static cost)

    Returns:
        {
            "final_usd": float,           # USED por CFO en gates
            "llm_estimate": float,
            "static_unit_cost": float | None,
            "historical_avg": float | None,
            "historical_p95": float | None,
            "source": "static|historical|llm|max_of_all",
            "reasoning": str,
        }
    """
    action_type = action.get("type", "unknown")
    quantity = float(action.get("quantity", 1))
    llm_est = float(action.get("estimated_spend_usd", 0) or 0)

    static_unit = STATIC_COSTS.get(action_type)
    static_total = (static_unit * quantity) if static_unit is not None else None

    hist_avg = get_historical_avg(action_type)
    hist_p95 = get_historical_p95(action_type)

    candidates = []
    sources = []
    if static_total is not None:
        candidates.append(static_total)
        sources.append("static")
    if hist_p95 is not None:
        # p95 mas conservador que avg
        candidates.append(hist_p95)
        sources.append("historical_p95")
    if hist_avg is not None:
        candidates.append(hist_avg)
        sources.append("historical_avg")
    candidates.append(llm_est)
    sources.append("llm")

    final = max(candidates) if candidates else 0
    if final == static_total:
        primary = "static"
    elif final == hist_p95:
        primary = "historical_p95"
    elif final == hist_avg:
        primary = "historical_avg"
    else:
        primary = "llm"

    return {
        "final_usd": round(final, 4),
        "llm_estimate": llm_est,
        "static_unit_cost": static_unit,
        "static_total": static_total,
        "historical_avg": hist_avg,
        "historical_p95": hist_p95,
        "source": primary,
        "all_sources": sources,
        "reasoning": (
            f"Took max of {sources}: ${final:.4f} via {primary}. "
            f"LLM estimated ${llm_est:.4f}."
        ),
    }


def ledger_snapshot() -> dict:
    """Para inyectar al ctx de constitution_validator."""
    if not LEDGER.exists():
        return {"lifetime_spent_usd": 0, "spent_last_24h_usd": 0,
                "spent_last_1h_usd": 0, "api_calls_last_min": 0}
    from datetime import datetime, timedelta
    con = _connect()
    now = datetime.utcnow()
    lifetime = con.execute("SELECT COALESCE(SUM(amount_usd),0) FROM spend").fetchone()[0]
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    cutoff_1h = (now - timedelta(hours=1)).isoformat()
    cutoff_1m = (now - timedelta(minutes=1)).isoformat()
    last_24h = con.execute("SELECT COALESCE(SUM(amount_usd),0) FROM spend WHERE ts>=?",
                            (cutoff_24h,)).fetchone()[0]
    last_1h = con.execute("SELECT COALESCE(SUM(amount_usd),0) FROM spend WHERE ts>=?",
                          (cutoff_1h,)).fetchone()[0]
    calls_1m = con.execute("SELECT COUNT(*) FROM spend WHERE ts>=?",
                            (cutoff_1m,)).fetchone()[0]
    con.close()
    return {
        "lifetime_spent_usd": float(lifetime),
        "spent_last_24h_usd": float(last_24h),
        "spent_last_1h_usd": float(last_1h),
        "api_calls_last_min": int(calls_1m),
    }


if __name__ == "__main__":
    # Test
    action = {
        "type": "claude_sonnet_call",
        "estimated_spend_usd": 0.001,  # LLM subestima
        "quantity": 5,
    }
    res = oracle_estimate(action)
    import json
    print(json.dumps(res, indent=2))
    print("\nLedger snapshot:", ledger_snapshot())
