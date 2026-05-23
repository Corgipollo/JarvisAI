"""vault_summarize.py - parsea vault_audit_report.txt y saca TOP proyectos.

Lee el reporte 81KB generado por findstr en CerebroEmmanuel y produce:
  - TOP-N proyectos por # de menciones de pendientes/TODO/FIXME
  - sample de 3 lineas por proyecto para contexto
  - output JSON ordenado por prioridad
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


REPORT = Path(r"C:\Users\Emmanuel\Documents\JarvisAI\data\reports\vault_audit_report.txt")
OUT = Path(r"C:\Users\Emmanuel\Documents\JarvisAI\data\reports\vault_top_projects.json")

PATTERN = re.compile(r"01-Proyectos[\\/]([A-Za-z0-9_\-]+)")


def main(top_n: int = 10) -> dict:
    if not REPORT.exists():
        print(f"FAIL: no existe {REPORT}", file=sys.stderr)
        sys.exit(1)

    text = REPORT.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    counter: Counter[str] = Counter()
    samples: dict[str, list[str]] = defaultdict(list)

    for ln in lines:
        m = PATTERN.search(ln)
        if not m:
            continue
        proj = m.group(1)
        counter[proj] += 1
        if len(samples[proj]) < 3:
            sample = ln.strip()
            if len(sample) > 200:
                sample = sample[:200] + "..."
            samples[proj].append(sample)

    top = counter.most_common(top_n)
    result = {
        "total_proyectos_con_pendientes": len(counter),
        "total_lineas_match": sum(counter.values()),
        "top": [
            {
                "proyecto": p,
                "menciones": c,
                "samples": samples[p],
            }
            for p, c in top
        ],
        "todos_proyectos": [
            {"proyecto": p, "menciones": c}
            for p, c in counter.most_common()
        ],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                    encoding="utf-8")
    print(f"OK: {len(counter)} proyectos, {sum(counter.values())} lineas")
    print(f"Output: {OUT}\n")
    print("TOP:")
    for entry in result["top"]:
        print(f"  {entry['menciones']:>4}x  {entry['proyecto']}")
    return result


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    main(n)
