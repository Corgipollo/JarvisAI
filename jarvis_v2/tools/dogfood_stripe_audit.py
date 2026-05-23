"""dogfood_stripe_audit.py - Primera auditoria real del debate_engine.

Extrae las secciones criticas de stripe_billing.py (auth + webhook +
checkout-session) y las somete al tribunal interno. Guarda reporte en
data/reports/debate_stripe_billing_audit.md.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SRC = ROOT / "jarvis_v2" / "api" / "stripe_billing.py"
REPORT = ROOT / "data" / "reports" / "debate_stripe_billing_audit.md"

FOCUS = (
    "Seguridad en manejo de Webhooks de Stripe y validacion de firmas. "
    "Buscar: bypass de stripe-signature verify, demo_mode que acepta JSON "
    "sin firma en produccion, race conditions en UPDATE tenant_meta, falta "
    "de idempotency en webhook (mismo event_id procesado 2 veces), SQL "
    "injection en tenant_id no validado, leak de stripe_customer_id en "
    "respuestas, manejo incorrecto de eventos inesperados."
)


def extract_critical(src_text: str) -> str:
    """Extrae auth + checkout-session + webhook handler completos."""
    lines = src_text.split("\n")
    out_parts: list[str] = []

    # Auth helper
    for i, line in enumerate(lines):
        if "def _auth" in line:
            j = i
            while j < len(lines) and (j == i or lines[j].startswith(" ")
                                          or lines[j].strip() == ""):
                out_parts.append(lines[j])
                j += 1
                if j - i > 6:
                    break
            break

    # checkout-session handler
    for i, line in enumerate(lines):
        if "def create_checkout_session" in line:
            j = i
            while j < len(lines):
                out_parts.append(lines[j])
                j += 1
                # corta cuando arranca proxima funcion top-level
                if j < len(lines) and (lines[j].startswith("def ")
                                           or lines[j].startswith("@router")):
                    break
                if j - i > 60:
                    break
            out_parts.append("")
            break

    # webhook handler
    for i, line in enumerate(lines):
        if "def stripe_webhook" in line:
            j = i
            while j < len(lines):
                out_parts.append(lines[j])
                j += 1
                if j < len(lines) and (lines[j].startswith("def ")
                                           or lines[j].startswith("@router")):
                    break
                if j - i > 80:
                    break
            break

    return "\n".join(out_parts)


def main() -> dict:
    src = SRC.read_text(encoding="utf-8")
    snippet = extract_critical(src)
    print(f"[dogfood] extracted {len(snippet)} chars de stripe_billing.py",
          flush=True)
    print(f"[dogfood] foco: {FOCUS[:100]}...", flush=True)

    from jarvis_v2.core.debate_engine import debate
    result = debate(snippet, focus_areas=FOCUS, max_rounds=2,
                     model="claude-haiku-4-5-20251001")

    # Genera reporte markdown
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    md_lines = [
        f"# Audit: stripe_billing.py — Debate Engine Dogfooding",
        f"",
        f"**Fecha**: {ts}",
        f"**Archivo**: `jarvis_v2/api/stripe_billing.py`",
        f"**Foco**: {FOCUS}",
        f"**Modelo**: claude-haiku-4-5-20251001",
        f"",
        f"---",
        f"",
        f"## Veredicto",
        f"",
        f"**Aprobado**: {'✅ SI' if result.get('approved') else '❌ NO'}",
        f"**Rounds ejecutados**: {result.get('rounds', 0)}/2",
        f"",
        f"## Razonamiento",
        f"",
        f"{result.get('reasoning', '(sin razonamiento)')}",
        f"",
        f"## Issues encontrados ({len(result.get('issues_found', []))})",
        f"",
    ]
    issues = result.get("issues_found") or []
    if issues:
        for i, iss in enumerate(issues, 1):
            sev = iss.get("severity", "?")
            desc = iss.get("description", "?")
            md_lines.append(f"### {i}. [{sev.upper()}] {desc}")
            md_lines.append("")
    else:
        md_lines.append("_Ninguno._")
        md_lines.append("")

    resolved = result.get("issues_resolved") or []
    md_lines.append(f"## Issues resueltos por Proposer ({len(resolved)})")
    md_lines.append("")
    if resolved:
        for i, iss in enumerate(resolved, 1):
            md_lines.append(f"- [{iss.get('severity', '?')}] {iss.get('description', '?')}")
        md_lines.append("")
    else:
        md_lines.append("_Ninguno (o no se necesitaron rondas adicionales)._")
        md_lines.append("")

    # Refactored code si hubo
    if result.get("final_code"):
        md_lines.append("## Codigo refactorizado por Proposer")
        md_lines.append("")
        md_lines.append("```python")
        md_lines.append(result["final_code"][:5000])
        md_lines.append("```")
        md_lines.append("")

    md_lines.append("---")
    md_lines.append("")
    md_lines.append("## Codigo auditado (extracto)")
    md_lines.append("")
    md_lines.append("```python")
    md_lines.append(snippet[:3000])
    if len(snippet) > 3000:
        md_lines.append(f"\n... [{len(snippet) - 3000} chars trimmed] ...")
    md_lines.append("```")

    REPORT.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"[dogfood] reporte escrito en {REPORT}", flush=True)
    print(f"[dogfood] approved={result.get('approved')} "
          f"rounds={result.get('rounds')} "
          f"issues={len(issues)}", flush=True)
    return result


if __name__ == "__main__":
    r = main()
    print(json.dumps({"approved": r.get("approved"),
                      "rounds": r.get("rounds"),
                      "issues_count": len(r.get("issues_found") or []),
                      "report": str(REPORT)},
                     ensure_ascii=False, indent=2))
