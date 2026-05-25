"""lead_research_writer.py - Produce 1 .md tangible con leads + research.

Flujo end-to-end tangible (responde a la directiva Grop "outputs visibles"):
  1. GET /api/v1/outreach/leads?limit=5
  2. Para cada lead, deep_research del email publico
  3. Escribe data/reports/leads_research_{YYYYMMDD_HHMM}.md

Disenado para encolarse via 'shell' action: el task_worker lo ejecuta y
el .md final es la PRUEBA de que el sistema produjo trabajo util.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

API_URL = "http://127.0.0.1:5000"
API_TOKEN = "jarvis_a8x29kfp3lz7m2qw9bdv"
REPORT_DIR = ROOT / "data" / "reports"


def get_leads(limit: int = 5) -> list[dict]:
    try:
        r = requests.get(
            f"{API_URL}/api/v1/outreach/leads",
            headers={"X-Jarvis-Token": API_TOKEN},
            params={"limit": limit},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        leads = data.get("leads", []) if isinstance(data, dict) else data
        return leads[:limit]
    except Exception as e:
        print(f"[lead_research] get_leads fail: {e}", file=sys.stderr)
        return []


def research_lead(lead: dict) -> dict:
    """Si lead no tiene email, busca via auto_research.deep_research."""
    out = {"company": lead.get("company"),
           "vertical": lead.get("vertical"),
           "existing_email": lead.get("contact_email") or "",
           "research_done": False,
           "found_emails": [],
           "summary": ""}
    if out["existing_email"]:
        out["summary"] = "ya tiene email registrado"
        return out
    try:
        from jarvis_v2.skills.auto_research import deep_research
        company = lead.get("company", "?")
        vertical = lead.get("vertical", "")
        query = f"{company} {vertical} contacto COO email LinkedIn site:linkedin.com OR site:zoominfo.com"
        r = deep_research(query, max_results=5)
        out["research_done"] = True
        out["summary"] = (r.get("synthesis") or "")[:600]
        # Heuristica: extraer emails del texto sintesis + snippets
        import re
        text = (r.get("synthesis", "") + " " +
                " ".join(item.get("snippet", "") for item in r.get("results", [])))
        emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)
        out["found_emails"] = list(dict.fromkeys(emails))[:3]  # dedup, top 3
    except Exception as e:
        out["summary"] = f"research_error: {e}"
    return out


def write_report(results: list[dict]) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    path = REPORT_DIR / f"leads_research_{ts}.md"
    lines = [
        f"# Lead Research Live — {ts}",
        f"",
        f"> Generado por `scripts/lead_research_writer.py` via task_worker.",
        f"> Total leads procesados: **{len(results)}**",
        f"",
        "---",
        "",
    ]
    found_count = 0
    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. {r.get('company', '?')} ({r.get('vertical', '')})")
        lines.append(f"")
        existing = r.get("existing_email", "")
        if existing:
            lines.append(f"- ✅ Email registrado: `{existing}`")
        else:
            lines.append(f"- ⚠️ Sin email registrado.")
            if r.get("found_emails"):
                found_count += 1
                lines.append(f"- 🔍 Emails encontrados via research:")
                for e in r["found_emails"]:
                    lines.append(f"  - `{e}`")
        if r.get("summary"):
            lines.append(f"- **Síntesis**: {r['summary']}")
        lines.append("")
    lines.append("---")
    lines.append(f"")
    lines.append(f"**Stats**: {found_count}/{len(results)} leads sin email recuperaron candidatos via research.")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    print(f"[lead_research] start at {datetime.utcnow().isoformat()}")
    leads = get_leads(limit=5)
    print(f"[lead_research] got {len(leads)} leads")
    if not leads:
        print("[lead_research] NO leads to process — abort", file=sys.stderr)
        sys.exit(1)
    results = []
    for i, lead in enumerate(leads, 1):
        print(f"[lead_research] [{i}/{len(leads)}] {lead.get('company', '?')}")
        r = research_lead(lead)
        results.append(r)
        time.sleep(0.5)  # gentil con DDG
    path = write_report(results)
    print(f"[lead_research] DONE: {path}")
    print(f"[lead_research] size: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
