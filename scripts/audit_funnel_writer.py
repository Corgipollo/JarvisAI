"""audit_funnel_writer.py - Produce snapshot tangible del funnel multi-tenant.

Flujo:
  1. GET /tenants -> lista todos los tenants
  2. Para cada uno, GET /tenants/{id}/summary
  3. Calcula conversion por etapa (signup -> demo -> active)
  4. Escribe data/reports/funnel_audit_{YYYYMMDD_HHMM}.md

Output replicable por encolar:
  shell: python scripts/audit_funnel_writer.py
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

API_URL = "http://127.0.0.1:5000"
API_TOKEN = "jarvis_a8x29kfp3lz7m2qw9bdv"
REPORT_DIR = ROOT / "data" / "reports"
HEADERS = {"X-Jarvis-Token": API_TOKEN}


def get_tenants() -> list[dict]:
    try:
        r = requests.get(f"{API_URL}/api/v1/tenants", headers=HEADERS, timeout=10)
        r.raise_for_status()
        d = r.json()
        return d.get("tenants", []) if isinstance(d, dict) else d
    except Exception as e:
        print(f"[funnel] get_tenants fail: {e}", file=sys.stderr)
        return []


def get_summary(tenant_id: str) -> dict:
    try:
        r = requests.get(
            f"{API_URL}/api/v1/tenants/{tenant_id}/summary",
            headers=HEADERS, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def classify(t: dict, summary: dict) -> str:
    """Etapa funnel: signup | demo | active | churned | unknown."""
    if summary.get("error"):
        return "unknown"
    status = (summary.get("stripe_subscription_status")
              or t.get("status") or "").lower()
    if status == "active":
        return "active"
    if status in ("trialing", "demo"):
        return "demo"
    if status in ("canceled", "incomplete_expired", "unpaid"):
        return "churned"
    return "signup"


def main():
    print(f"[funnel] start at {datetime.utcnow().isoformat()}")
    tenants = get_tenants()
    print(f"[funnel] got {len(tenants)} tenants")

    rows = []
    stages = {"signup": 0, "demo": 0, "active": 0, "churned": 0, "unknown": 0}
    revenue_mtd = 0.0
    for t in tenants:
        tid = t.get("tenant_id") or t.get("id") or t.get("name") or "?"
        summary = get_summary(tid)
        stage = classify(t, summary)
        stages[stage] += 1
        revenue_mtd += float(summary.get("revenue_mtd_usd", 0) or 0)
        rows.append({"id": tid, "name": t.get("name", tid), "stage": stage,
                     "summary": summary})

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    path = REPORT_DIR / f"funnel_audit_{ts}.md"

    total = max(1, sum(stages.values()))
    lines = [
        f"# Funnel Audit — {ts}",
        f"",
        f"> Generado por `scripts/audit_funnel_writer.py`",
        f"> Total tenants: **{len(tenants)}** | Revenue MTD: **${revenue_mtd:.2f}**",
        f"",
        f"## Funnel por etapa",
        f"",
        f"| Etapa | Count | % |",
        f"|---|---|---|",
        f"| Signup (no demo) | {stages['signup']} | {100*stages['signup']/total:.0f}% |",
        f"| Demo (trial) | {stages['demo']} | {100*stages['demo']/total:.0f}% |",
        f"| Active (pagando) | {stages['active']} | {100*stages['active']/total:.0f}% |",
        f"| Churned | {stages['churned']} | {100*stages['churned']/total:.0f}% |",
        f"| Unknown | {stages['unknown']} | {100*stages['unknown']/total:.0f}% |",
        f"",
        f"## Conversion rates",
        f"",
    ]
    if stages["signup"] + stages["demo"] > 0:
        conv_demo = 100 * stages["demo"] / (stages["signup"] + stages["demo"])
        lines.append(f"- Signup -> Demo: **{conv_demo:.1f}%**")
    if stages["demo"] + stages["active"] > 0:
        conv_active = 100 * stages["active"] / (stages["demo"] + stages["active"])
        lines.append(f"- Demo -> Active: **{conv_active:.1f}%**")
    lines.extend(["", "## Tenants detalle", ""])
    for r in rows:
        lines.append(f"### {r['name']} (`{r['id']}`) — {r['stage']}")
        s = r["summary"]
        if s.get("error"):
            lines.append(f"  - error obteniendo summary: {s['error']}")
        else:
            lines.append(f"  - revenue_mtd: ${s.get('revenue_mtd_usd', 0):.2f}")
            lines.append(f"  - signups: {s.get('signups_total', 0)}")
            lines.append(f"  - last_active: {s.get('last_active_at', '?')}")
        lines.append("")

    lines.extend([
        "---",
        "",
        f"**Insight**: {stages['active']} de {total} tenants pagando = "
        f"{100*stages['active']/total:.0f}% activation rate. "
        f"{'OK' if stages['active']/total > 0.1 else 'Bajo, requiere atencion outreach'}.",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[funnel] DONE: {path}")
    print(f"[funnel] size: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
