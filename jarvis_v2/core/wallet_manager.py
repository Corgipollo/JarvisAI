"""wallet_manager.py - Control de presupuesto operativo para Jarvis.

ESTADO: STUB CONTROLADO. Budget=$0 por default. Toda peticion de gasto
retorna approved=False con razon "no_budget_configured" hasta que
Emmanuel inyecte fondos reales via env var o config file.

POR QUE STUB:
  - Privacy.com (la sugerencia comun) NO opera en Mexico. Emmanuel es MX.
    Equivalentes reales LATAM: Klar (MX), Mercury (US business), Wise
    multi-currency virtual cards, Revolut Business.
  - $0 budget evaluando ROI es matematicamente vacio. Sin dato real, el
    agente no puede priorizar.
  - Sin facturacion real (Jarvis V2 no tiene clientes pagando todavia),
    cualquier gasto es perdida. La regla "gasta $1 si ROI positivo"
    requiere primero medir baseline de revenue, lo cual no existe.

CUANDO ACTIVAR (checklist):
  [ ] Jarvis V2 tiene >= 1 cliente pagando (MRR > $0)
  [ ] Existe trayectoria de conversion outreach -> demo -> cliente con N>=10
  [ ] Emmanuel tiene virtual card (Klar / Wise / Mercury) lista
  [ ] Emmanuel define monthly_budget_usd en wallet_config.json o env var
  [ ] Existe baseline_revenue_per_lead para que ROI tenga denominador

API (lista para usarse el dia que se inyecte budget):

    get_balance() -> {balance_usd, reserved_usd, available_usd, currency, budget_source}

    can_afford(amount_usd, reason, vendor=None) -> {ok, reason, available_usd}

    request_spend(amount_usd, reason, vendor, expected_roi=None) -> {
        approved: bool,
        spend_id: str | None,
        reason: str,
        ledger_entry: dict | None,
    }
        Si approved=True, descuenta del reserved y agrega entry al ledger.
        El gasto REAL (ejecutar el pago) NO ocurre aqui — es responsabilidad
        del caller usando la spend_id como autorizacion.

    record_outcome(spend_id, success: bool, actual_revenue=None) -> None
        El caller reporta el resultado del gasto. Si success y revenue>amount,
        el ROI queda registrado para training del approval algorithm.

    ledger(limit=50) -> list[entry]
        Historico de spend requests + outcomes.

Config sources (en orden de prioridad):
  1. Env var JARVIS_WALLET_BUDGET_USD (numero) — override rapido
  2. data/wallet_config.json — config persistente
  3. Default = 0.0

Schema wallet_config.json:
    {
      "monthly_budget_usd": 50.0,
      "currency": "USD",
      "auto_approve_under_usd": 1.0,
      "vendors_whitelist": ["openai.com", "anthropic.com", "scrapingbee.com"],
      "vendors_blacklist": [],
      "require_positive_roi_above_usd": 5.0,
      "card_provider": "klar_mx"
    }
"""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "data" / "wallet_config.json"
LEDGER_FILE = ROOT / "data" / "wallet_ledger.jsonl"
STATE_FILE = ROOT / "data" / "wallet_state.json"


DEFAULT_CONFIG = {
    "monthly_budget_usd": 0.0,
    "currency": "USD",
    "auto_approve_under_usd": 0.0,
    "vendors_whitelist": [],
    "vendors_blacklist": [],
    "require_positive_roi_above_usd": 1.0,
    "card_provider": "none",
}


def _load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    env_budget = os.environ.get("JARVIS_WALLET_BUDGET_USD")
    if env_budget:
        try:
            cfg["monthly_budget_usd"] = float(env_budget)
        except Exception:
            pass
    return cfg


def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {"month": _current_month(), "spent_usd": 0.0, "reserved_usd": 0.0}
    try:
        st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"month": _current_month(), "spent_usd": 0.0, "reserved_usd": 0.0}
    if st.get("month") != _current_month():
        # Rollover: reset spent for new month, keep reservations
        st = {"month": _current_month(), "spent_usd": 0.0,
              "reserved_usd": float(st.get("reserved_usd", 0.0))}
    return st


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _current_month() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _append_ledger(entry: dict) -> None:
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def get_balance() -> dict:
    cfg = _load_config()
    state = _load_state()
    budget = float(cfg["monthly_budget_usd"])
    spent = float(state.get("spent_usd", 0.0))
    reserved = float(state.get("reserved_usd", 0.0))
    available = max(0.0, budget - spent - reserved)
    return {
        "balance_usd": budget - spent,
        "budget_usd": budget,
        "spent_usd": spent,
        "reserved_usd": reserved,
        "available_usd": available,
        "currency": cfg["currency"],
        "month": state["month"],
        "card_provider": cfg["card_provider"],
        "budget_source": "env" if os.environ.get("JARVIS_WALLET_BUDGET_USD")
                          else "config_file" if CONFIG_FILE.exists() else "default_zero",
        "active": budget > 0,
    }


def can_afford(amount_usd: float, reason: str = "",
                vendor: str | None = None) -> dict:
    balance = get_balance()
    if not balance["active"]:
        return {"ok": False, "reason": "no_budget_configured",
                "next_step": "Set JARVIS_WALLET_BUDGET_USD env var "
                              "or create data/wallet_config.json with "
                              "monthly_budget_usd > 0"}
    if amount_usd > balance["available_usd"]:
        return {"ok": False, "reason": "insufficient_funds",
                "amount_usd": amount_usd,
                "available_usd": balance["available_usd"]}
    cfg = _load_config()
    if vendor and vendor in cfg["vendors_blacklist"]:
        return {"ok": False, "reason": "vendor_blacklisted", "vendor": vendor}
    if cfg["vendors_whitelist"] and vendor not in cfg["vendors_whitelist"]:
        return {"ok": False, "reason": "vendor_not_whitelisted", "vendor": vendor,
                "whitelist": cfg["vendors_whitelist"]}
    return {"ok": True, "amount_usd": amount_usd,
            "available_usd": balance["available_usd"]}


def request_spend(amount_usd: float, reason: str, vendor: str,
                   expected_roi: float | None = None) -> dict:
    check = can_afford(amount_usd, reason, vendor)
    if not check["ok"]:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "type": "denied",
            "amount_usd": amount_usd,
            "vendor": vendor,
            "reason_request": reason,
            "denial_reason": check["reason"],
            "expected_roi": expected_roi,
        }
        _append_ledger(entry)
        return {"approved": False, "reason": check["reason"],
                "ledger_entry": entry, "spend_id": None}

    cfg = _load_config()
    if (amount_usd > cfg["require_positive_roi_above_usd"]
            and (expected_roi is None or expected_roi <= 1.0)):
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "type": "denied",
            "amount_usd": amount_usd,
            "vendor": vendor,
            "reason_request": reason,
            "denial_reason": "roi_unjustified",
            "expected_roi": expected_roi,
        }
        _append_ledger(entry)
        return {"approved": False, "reason": "roi_unjustified",
                "ledger_entry": entry, "spend_id": None}

    spend_id = "sp_" + secrets.token_urlsafe(10)
    state = _load_state()
    state["reserved_usd"] = float(state.get("reserved_usd", 0.0)) + amount_usd
    _save_state(state)

    entry = {
        "ts": datetime.utcnow().isoformat(),
        "type": "reserved",
        "spend_id": spend_id,
        "amount_usd": amount_usd,
        "vendor": vendor,
        "reason_request": reason,
        "expected_roi": expected_roi,
    }
    _append_ledger(entry)
    return {"approved": True, "spend_id": spend_id, "reason": "approved_reserved",
            "ledger_entry": entry,
            "next_step": "execute payment externally, then call record_outcome(spend_id, success, actual_revenue)"}


def record_outcome(spend_id: str, success: bool,
                    actual_revenue: float | None = None,
                    notes: str = "") -> dict:
    state = _load_state()
    # Find original reservation amount (scan ledger)
    amount = 0.0
    if LEDGER_FILE.exists():
        for line in LEDGER_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
                if e.get("spend_id") == spend_id and e.get("type") == "reserved":
                    amount = float(e.get("amount_usd", 0.0))
                    break
            except Exception:
                continue
    if amount == 0.0:
        return {"ok": False, "reason": "spend_id_not_found"}

    state["reserved_usd"] = max(0.0, float(state.get("reserved_usd", 0.0)) - amount)
    if success:
        state["spent_usd"] = float(state.get("spent_usd", 0.0)) + amount
    _save_state(state)

    entry = {
        "ts": datetime.utcnow().isoformat(),
        "type": "outcome",
        "spend_id": spend_id,
        "amount_usd": amount,
        "success": success,
        "actual_revenue_usd": actual_revenue,
        "roi": (actual_revenue / amount) if (actual_revenue and amount) else None,
        "notes": notes,
    }
    _append_ledger(entry)
    return {"ok": True, "entry": entry, "new_state": state}


def ledger(limit: int = 50) -> list[dict]:
    if not LEDGER_FILE.exists():
        return []
    lines = LEDGER_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--balance", action="store_true")
    p.add_argument("--ledger", action="store_true")
    p.add_argument("--simulate-spend", type=float, default=None,
                    help="Simula request_spend con monto USD")
    p.add_argument("--vendor", default="test_vendor")
    p.add_argument("--reason", default="smoke test")
    args = p.parse_args()

    if args.balance:
        print(json.dumps(get_balance(), indent=2))
    elif args.ledger:
        print(json.dumps(ledger(), indent=2, ensure_ascii=False, default=str))
    elif args.simulate_spend is not None:
        r = request_spend(args.simulate_spend, args.reason, args.vendor,
                           expected_roi=2.0)
        print(json.dumps(r, indent=2, ensure_ascii=False, default=str))
    else:
        print(json.dumps(get_balance(), indent=2))
