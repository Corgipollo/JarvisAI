"""omniparser_researcher.py - I+D perpetuo cada 12h.

Despierta -> consulta GitHub + arXiv + HN sin autenticacion -> compara con
estado cacheado en data/omniparser_research_state.json -> si hay novedad
relevante, llama brain una vez para evaluar significancia y escribe
data/reports/omniparser_upgrades.md (append-only).

Fuentes consultadas (publicas, sin API key):
  - GitHub Search API: repos OmniParser + gui-agent + computer-use, sort stars
  - arXiv API: papers recientes con keywords
  - HN Algolia: discusiones recientes

Costo por ejecucion: 0 a 1 call brain (Haiku). Si no hay novedad: $0.
Registrado como schtask 'Jarvis_ID_Perpetuo' cada 12h.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

STATE_PATH = ROOT / "data" / "omniparser_research_state.json"
REPORT_PATH = ROOT / "data" / "reports" / "omniparser_upgrades.md"
LOG_PATH = ROOT / "data" / "omniparser_researcher.log"

KEYWORDS = ["omniparser", "gui agent", "computer use", "ui-ed",
            "screen agent", "ui element detection"]


def _log(msg: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"github_known_ids": [], "arxiv_known_ids": [],
                "hn_known_ids": [], "last_run": None}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"github_known_ids": [], "arxiv_known_ids": [],
                "hn_known_ids": [], "last_run": None}


def _save_state(s: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    s["last_run"] = datetime.utcnow().isoformat()
    STATE_PATH.write_text(json.dumps(s, ensure_ascii=False, indent=2),
                          encoding="utf-8")


def _github_search(query: str, limit: int = 8) -> list[dict]:
    """Public GitHub search. Sin token: 10 req/min limite. Suficiente."""
    url = "https://api.github.com/search/repositories"
    params = {"q": f"{query} pushed:>2026-04-01",
              "sort": "stars", "order": "desc", "per_page": limit}
    try:
        with httpx.Client(timeout=15) as cli:
            r = cli.get(url, params=params,
                        headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            _log(f"github http {r.status_code}: {r.text[:200]}")
            return []
        return r.json().get("items", [])
    except Exception as e:
        _log(f"github error: {e}")
        return []


def _arxiv_search(query: str, limit: int = 8) -> list[dict]:
    """arXiv public API. No auth. Devuelve papers recientes."""
    import re
    q = "+OR+".join([f'all:"{k}"' for k in query.split()])
    url = ("http://export.arxiv.org/api/query?"
           f"search_query={q}&start=0&max_results={limit}"
           "&sortBy=submittedDate&sortOrder=descending")
    try:
        with httpx.Client(timeout=20) as cli:
            r = cli.get(url)
        if r.status_code != 200:
            return []
        # parse XML mini (sin lxml dep)
        entries = re.findall(r"<entry>(.*?)</entry>", r.text, re.DOTALL)
        out = []
        for e in entries[:limit]:
            id_m = re.search(r"<id>(.*?)</id>", e)
            t_m = re.search(r"<title>(.*?)</title>", e, re.DOTALL)
            d_m = re.search(r"<published>(.*?)</published>", e)
            s_m = re.search(r"<summary>(.*?)</summary>", e, re.DOTALL)
            if id_m:
                out.append({
                    "id": id_m.group(1).strip(),
                    "title": (t_m.group(1).strip() if t_m else "?")[:200],
                    "published": d_m.group(1).strip() if d_m else "",
                    "summary": (s_m.group(1).strip() if s_m else "")[:400],
                })
        return out
    except Exception as e:
        _log(f"arxiv error: {e}")
        return []


def _hn_search(query: str, limit: int = 5) -> list[dict]:
    url = "https://hn.algolia.com/api/v1/search"
    params = {"query": query, "tags": "story",
              "numericFilters": "points>20", "hitsPerPage": limit}
    try:
        with httpx.Client(timeout=15) as cli:
            r = cli.get(url, params=params)
        if r.status_code != 200:
            return []
        return r.json().get("hits", [])
    except Exception as e:
        _log(f"hn error: {e}")
        return []


def _evaluate_with_brain(deltas: list[dict]) -> dict:
    """1 call al brain con el delta encontrado.

    Pide JSON {significant, summary, action}. Si brain falla, marca como
    no-significativo (best-effort fail-open).
    """
    try:
        from jarvis_bridge.jarvis_brain import ask_claude_json
    except ImportError:
        return {"significant": False, "summary": "brain unavailable"}
    prompt = (
        "Eres analista de I+D. Recibi este delta de novedades sobre "
        "OmniParser/Computer Use/GUI agents. Decide si justifica un upgrade "
        "del stack actual de Jarvis V2 (que usa OmniParser v2.0.1 + YOLO + "
        "Florence + closed-loop SSIM).\n\n"
        f"DELTAS:\n{json.dumps(deltas[:10], ensure_ascii=False, indent=2)[:4000]}\n\n"
        'Responde JSON: {"significant": true|false, "summary": "1-2 lineas '
        'que cambio relevante", "action": "monitor|propose_refactor|urgent_upgrade"}'
    )
    out = ask_claude_json(
        prompt,
        system="Eres analista IA. Conciso, JSON puro.",
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
    )
    if not out:
        return {"significant": False, "summary": "brain returned None"}
    return out


def _append_report(deltas: list[dict], evaluation: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    header_new = not REPORT_PATH.exists()
    with REPORT_PATH.open("a", encoding="utf-8") as f:
        if header_new:
            f.write("# OmniParser / GUI-Agent — Bitacora I+D Perpetuo\n\n")
            f.write("> Daemon `omniparser_researcher.py` ejecuta cada 12h. "
                    "Cada entrada es un delta detectado.\n\n---\n\n")
        f.write(f"## {ts}\n\n")
        f.write(f"**Evaluacion**: {evaluation.get('summary', '?')}\n\n")
        f.write(f"**Action recomendada**: `{evaluation.get('action', 'monitor')}`\n\n")
        f.write(f"**Significativo**: {evaluation.get('significant', False)}\n\n")
        f.write(f"### Deltas detectados ({len(deltas)})\n\n")
        for d in deltas[:15]:
            src = d.get("source", "?")
            title = d.get("title") or d.get("name") or d.get("id", "?")
            url = d.get("url") or d.get("html_url") or d.get("id", "")
            stars = d.get("stargazers_count")
            extra = f" (stars: {stars})" if stars else ""
            f.write(f"- **[{src}]** {title}{extra} - {url}\n")
        f.write("\n---\n\n")


def main() -> dict:
    _log("=== I+D perpetuo cycle start ===")
    state = _load_state()

    new_items: list[dict] = []
    # GitHub: 2 queries
    for q in ["omniparser", "gui agent computer use"]:
        for item in _github_search(q):
            iid = item.get("id")
            if iid and iid not in state["github_known_ids"]:
                state["github_known_ids"].append(iid)
                new_items.append({
                    "source": "github",
                    "name": item.get("full_name"),
                    "stargazers_count": item.get("stargazers_count"),
                    "html_url": item.get("html_url"),
                    "description": (item.get("description") or "")[:200],
                })

    # arXiv
    for paper in _arxiv_search("omniparser gui agent"):
        if paper["id"] and paper["id"] not in state["arxiv_known_ids"]:
            state["arxiv_known_ids"].append(paper["id"])
            new_items.append({"source": "arxiv", **paper})

    # HN
    for hit in _hn_search("omniparser OR \"computer use\" OR \"gui agent\""):
        oid = hit.get("objectID")
        if oid and oid not in state["hn_known_ids"]:
            state["hn_known_ids"].append(oid)
            new_items.append({
                "source": "hn",
                "title": hit.get("title"),
                "url": hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                "points": hit.get("points"),
            })

    # Caps: estado solo guarda hasta 500 ids para no crecer infinito
    for k in ("github_known_ids", "arxiv_known_ids", "hn_known_ids"):
        state[k] = state[k][-500:]

    _log(f"new items: {len(new_items)}")
    if not new_items:
        _save_state(state)
        return {"ok": True, "new_count": 0}

    # Evaluate
    evaluation = _evaluate_with_brain(new_items)
    _log(f"evaluation: {evaluation.get('significant')} - {evaluation.get('action')}")

    _append_report(new_items, evaluation)
    _save_state(state)

    # Notify si significant
    if evaluation.get("significant"):
        try:
            from jarvis_v2.bridges.telegram_notify import notify
            notify(f"I+D Jarvis: {evaluation.get('summary', '?')[:200]} "
                   f"[{evaluation.get('action', 'monitor')}] "
                   f"-> data/reports/omniparser_upgrades.md")
        except Exception:
            pass

    return {"ok": True, "new_count": len(new_items),
            "significant": evaluation.get("significant", False),
            "action": evaluation.get("action", "monitor")}


if __name__ == "__main__":
    r = main()
    print(json.dumps(r, ensure_ascii=False, indent=2))
