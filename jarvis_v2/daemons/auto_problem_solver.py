"""auto_problem_solver.py - Detecta bloqueadores activos y auto-investiga.

Cada hora:
  1. Escanea data/reports/ buscando "BLOQUEADOR", "ERROR", "FAIL", "TODO",
     "(faltante)", "pendiente" en archivos modificados ultimas 24h
  2. Lee alertas del PDF mas reciente (C:\\reportes\\jarvis_*.pdf metadata
     via re-extract de gather_business_state)
  3. Extrae los top 3 problemas activos no resueltos
  4. Para cada uno: deep_research() via auto_research.py
  5. Append findings a data/reports/auto_research_log.md

Registrado como schtask Jarvis_Problem_Solver cada 60 min.
Nunca pide permiso - cumple la directiva "siempre busca soluciones".
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Forzar UTF-8 en stdout/stderr (Windows cp1252 rompe con emojis o arrows unicode)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

REPORTS_DIR = ROOT / "data" / "reports"
RESEARCH_LOG = REPORTS_DIR / "auto_research_log.md"
SEEN_PROBLEMS_FILE = ROOT / "data" / "auto_problem_solver_seen.json"
MAX_PROBLEMS_PER_RUN = 3

# Patrones que indican un problema activo no resuelto
PROBLEM_PATTERNS = [
    (re.compile(r"^.*(BLOQUEADOR|BLOQUEADOR REAL)[:\s]+(.{20,200})", re.M), "bloqueador"),
    (re.compile(r"^.*ERROR[:\s]+(.{20,200})", re.M), "error"),
    (re.compile(r"^.*CRITICAL[:\s]+(.{20,200})", re.M), "critical"),
    (re.compile(r"^.*FAIL[A-Z]*[:\s]+(.{20,200})", re.M), "fail"),
    (re.compile(r"^\s*-\s*\[\s*\]\s*(.{20,200})", re.M), "pendiente"),
]


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _load_seen() -> set:
    if not SEEN_PROBLEMS_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_PROBLEMS_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def _save_seen(seen: set) -> None:
    SEEN_PROBLEMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Cap a 500 problemas vistos
    items = list(seen)[-500:]
    SEEN_PROBLEMS_FILE.write_text(json.dumps(items, ensure_ascii=False),
                                   encoding="utf-8")


def scan_reports_for_problems() -> list[dict]:
    """Escanea reports recientes + status.md + auto_decisions.log."""
    if not REPORTS_DIR.exists():
        return []
    problems = []
    cutoff = time.time() - 86400 * 2  # ultimas 48h
    for path in REPORTS_DIR.glob("*.md"):
        try:
            if path.stat().st_mtime < cutoff:
                continue
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for pattern, ptype in PROBLEM_PATTERNS:
            for m in pattern.finditer(content):
                text = m.group(m.lastindex).strip()
                # Filtra falsos positivos: muy cortos o solo markdown
                if len(text) < 20:
                    continue
                if text.startswith("#") or text.startswith("|"):
                    continue
                # Trim a primera frase
                text = re.split(r"(?<=[.!?])\s", text)[0][:200]
                problems.append({
                    "type": ptype,
                    "text": text,
                    "source": path.name,
                })
    return problems


def rank_problems(problems: list[dict]) -> list[dict]:
    """Prioriza: critical > error > bloqueador > fail > pendiente.
    Dedup por texto similar (primeros 60 chars)."""
    priority = {"critical": 5, "error": 4, "bloqueador": 3,
                "fail": 2, "pendiente": 1}
    seen_keys = set()
    ranked = []
    for p in sorted(problems, key=lambda x: -priority.get(x["type"], 0)):
        key = re.sub(r"[^\w\s]", "", p["text"][:60].lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        p["_key"] = key
        ranked.append(p)
    return ranked


def append_research_log(problem: dict, research: dict) -> None:
    RESEARCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    header_new = not RESEARCH_LOG.exists()
    with RESEARCH_LOG.open("a", encoding="utf-8") as f:
        if header_new:
            f.write("# Auto Research Log — Bitacora del Problem Solver\n\n")
            f.write("> Daemon `auto_problem_solver.py` cada 60 min escanea bloqueadores\n")
            f.write("> activos del sistema, hace deep_research y sintetiza alternativas.\n")
            f.write("> Append-only. Lectura humana opcional.\n\n---\n\n")
        ts = research.get("ts", "?")
        f.write(f"## {ts} — [{problem['type'].upper()}] {problem['source']}\n\n")
        f.write(f"**Problema detectado**: {problem['text']}\n\n")
        f.write(f"**Source research**: {research.get('source')} ({research.get('results_count', 0)} resultados, {research.get('elapsed_ms', 0)}ms)\n\n")
        f.write(f"### Sintesis\n\n{research.get('synthesis', '(sin sintesis)')}\n\n")
        results = research.get("results") or []
        if results:
            f.write("### Top hallazgos\n\n")
            for r in results[:5]:
                f.write(f"- **{r['title']}** — {r['snippet'][:150]} [{r['url']}]\n")
            f.write("\n")
        f.write("---\n\n")


def cycle_once() -> dict:
    _log("=== Problem Solver cycle start ===")
    problems = scan_reports_for_problems()
    _log(f"detectados {len(problems)} matches problema")
    if not problems:
        return {"ok": True, "researched": 0, "no_problems": True}

    ranked = rank_problems(problems)
    seen = _load_seen()
    fresh = [p for p in ranked if p["_key"] not in seen][:MAX_PROBLEMS_PER_RUN]
    _log(f"fresh (no vistos antes): {len(fresh)}")
    if not fresh:
        return {"ok": True, "researched": 0, "all_seen": True}

    from jarvis_v2.skills.auto_research import deep_research

    researched = 0
    for problem in fresh:
        # Construye query enfocada al problema
        query = (f"como resolver {problem['text'][:120]} 2026 "
                 "alternativas gratuitas open source")
        _log(f"  -> research: {query[:80]}")
        try:
            research = deep_research(query, max_results=6)
            append_research_log(problem, research)
            seen.add(problem["_key"])
            researched += 1
            time.sleep(3)  # rate limit polite entre búsquedas
        except Exception as e:
            _log(f"  research fail: {e}")
            continue

    _save_seen(seen)
    _log(f"=== Cycle end. Researched {researched}/{len(fresh)} ===")
    return {"ok": True, "researched": researched,
            "total_problems_seen_so_far": len(seen)}


if __name__ == "__main__":
    # Default: 1 ciclo + exit (schtask lo correra cada 60 min).
    # Pasa --loop para modo bucle continuo (debug)
    if "--loop" in sys.argv:
        cycle_min = 60
        while True:
            try:
                cycle_once()
            except Exception as e:
                _log(f"cycle EXCEPTION: {e}")
            _log(f"sleeping {cycle_min} min")
            time.sleep(cycle_min * 60)
    else:
        r = cycle_once()
        print(json.dumps(r, ensure_ascii=False, indent=2))
