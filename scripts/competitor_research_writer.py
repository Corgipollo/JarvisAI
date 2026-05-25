"""competitor_research_writer.py - Produce reporte de inteligencia competitiva.

Flujo:
  1. Define keywords/temas a investigar (rotativos cada vez via hash time)
  2. Para cada uno, auto_research.deep_research(query)
  3. Sintetiza hallazgos
  4. Escribe data/reports/competitors_{YYYYMMDD_HHMM}.md

Output replicable por encolar:
  shell: python scripts/competitor_research_writer.py [keyword]
"""
from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "data" / "reports"

# Pool rotativo de temas competitivos relevantes a Jarvis V2
# (agencia automatizacion + agro logistics + B2B SaaS LATAM)
DEFAULT_TOPICS = [
    "Anthropic Computer Use 2026 pricing competitors",
    "GUI agent benchmark Screen Spot Pro winners",
    "OmniParser update 2026 release notes",
    "vertical SaaS agentic LATAM market 2026",
    "Shopify multi-tenant agency model pricing 2026",
    "AutoDS dropshipping API changes 2026",
    "Remotion video automation pricing competitors",
    "n8n vs Zapier vs Make agencias automatizacion 2026",
]


def main():
    print(f"[competitors] start at {datetime.utcnow().isoformat()}")
    # Permitir override via argv
    if len(sys.argv) > 1:
        topics = [" ".join(sys.argv[1:])]
    else:
        # Rota: toma 3 temas distintos cada vez (seed por timestamp)
        random.seed(int(time.time()) // 3600)  # cambia cada hora
        topics = random.sample(DEFAULT_TOPICS, k=min(3, len(DEFAULT_TOPICS)))

    print(f"[competitors] researching {len(topics)} topics:")
    for t in topics:
        print(f"  - {t}")

    try:
        from jarvis_v2.skills.auto_research import deep_research
    except Exception as e:
        print(f"[competitors] auto_research import fail: {e}", file=sys.stderr)
        sys.exit(1)

    results = []
    for i, topic in enumerate(topics, 1):
        print(f"[competitors] [{i}/{len(topics)}] {topic}")
        try:
            r = deep_research(topic, max_results=5)
            results.append({
                "topic": topic,
                "source": r.get("source", "?"),
                "results_count": r.get("results_count", 0),
                "synthesis": (r.get("synthesis") or "")[:1200],
                "top_links": [
                    {"title": item.get("title", "")[:120],
                     "url": item.get("url", "")}
                    for item in (r.get("results") or [])[:3]
                ],
            })
        except Exception as e:
            results.append({"topic": topic, "error": str(e)})
        time.sleep(1)  # gentil con backends

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    path = REPORT_DIR / f"competitors_{ts}.md"

    lines = [
        f"# Competitive Intelligence — {ts}",
        f"",
        f"> Generado por `scripts/competitor_research_writer.py`",
        f"> Topics investigados: **{len(results)}**",
        f"",
        f"---",
        f"",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. {r['topic']}")
        lines.append(f"")
        if r.get("error"):
            lines.append(f"- ERROR: `{r['error']}`")
            lines.append("")
            continue
        lines.append(f"- **Source**: {r.get('source')} ({r.get('results_count')} resultados)")
        lines.append(f"")
        lines.append(f"### Síntesis")
        lines.append(f"")
        lines.append(r.get("synthesis", "(sin sintesis)"))
        lines.append(f"")
        if r.get("top_links"):
            lines.append(f"### Top hallazgos")
            for link in r["top_links"]:
                lines.append(f"- [{link['title']}]({link['url']})")
            lines.append("")
        lines.append("---")
        lines.append("")
    lines.append(f"**Generated at**: {datetime.utcnow().isoformat()}")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[competitors] DONE: {path}")
    print(f"[competitors] size: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
