"""auto_research.py - Skill de deep research sin API key.

Cascade:
  1. DuckDuckGo Lite HTML scrape (sin signup, public)
  2. Brave Search API si BRAVE_API_KEY existe (2K queries/mes free)
  3. Tavily API si TAVILY_API_KEY existe
  4. Fallback: brain razona con conocimiento propio + sin web

API:
    deep_research(query, max_results=8) -> dict
        {query, results: [{title, url, snippet}], synthesis, source}

Diseñado para correr autónomamente desde infinite_ceo o auto_problem_solver.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse, unquote, parse_qs

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BRAVE_KEY = os.environ.get("BRAVE_API_KEY", "")
TAVILY_KEY = os.environ.get("TAVILY_API_KEY", "")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")


def _ddg_lite(query: str, limit: int = 8) -> list[dict]:
    """DuckDuckGo Lite — interfaz minimal sin JS, menos bot detection."""
    url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query)}"
    try:
        with httpx.Client(timeout=15, follow_redirects=True,
                          headers={"User-Agent": UA}) as cli:
            r = cli.get(url)
        if r.status_code != 200:
            return []
        # Parse minimal: <a class="result-link" href="...">Title</a> seguido de snippet
        html = r.text
        results = []
        # Patron: links de resultado seguidos de snippets
        pattern = re.compile(
            r'<a\s+rel="nofollow"\s+href="([^"]+)"\s+class="result-link">([^<]+)</a>',
            re.IGNORECASE)
        snippet_pat = re.compile(
            r'<td\s+class="result-snippet">(.*?)</td>',
            re.IGNORECASE | re.DOTALL)
        link_matches = list(pattern.finditer(html))
        snippet_matches = list(snippet_pat.finditer(html))
        for i, lm in enumerate(link_matches[:limit]):
            raw_url = lm.group(1)
            # Strip DuckDuckGo redirect
            if "//duckduckgo.com/l/?uddg=" in raw_url:
                qs = parse_qs(urlparse(raw_url).query)
                raw_url = unquote(qs.get("uddg", [raw_url])[0])
            snippet = ""
            if i < len(snippet_matches):
                snippet = re.sub(r"<[^>]+>", " ", snippet_matches[i].group(1))
                snippet = re.sub(r"\s+", " ", snippet).strip()[:300]
            results.append({
                "title": re.sub(r"<[^>]+>", "", lm.group(2)).strip()[:200],
                "url": raw_url,
                "snippet": snippet,
            })
        return results
    except Exception as e:
        print(f"[auto_research] ddg_lite fail: {e}", file=sys.stderr)
        return []


def _brave_search(query: str, limit: int = 8) -> list[dict]:
    if not BRAVE_KEY:
        return []
    try:
        with httpx.Client(timeout=15, headers={
            "X-Subscription-Token": BRAVE_KEY,
            "Accept": "application/json",
        }) as cli:
            r = cli.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": limit})
        if r.status_code != 200:
            return []
        data = r.json()
        return [{
            "title": item.get("title", "")[:200],
            "url": item.get("url", ""),
            "snippet": item.get("description", "")[:300],
        } for item in data.get("web", {}).get("results", [])[:limit]]
    except Exception as e:
        print(f"[auto_research] brave fail: {e}", file=sys.stderr)
        return []


def _tavily_search(query: str, limit: int = 8) -> list[dict]:
    if not TAVILY_KEY:
        return []
    try:
        with httpx.Client(timeout=20) as cli:
            r = cli.post(
                "https://api.tavily.com/search",
                json={"api_key": TAVILY_KEY, "query": query,
                      "search_depth": "advanced", "max_results": limit})
        if r.status_code != 200:
            return []
        data = r.json()
        return [{
            "title": item.get("title", "")[:200],
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:300],
        } for item in data.get("results", [])[:limit]]
    except Exception as e:
        print(f"[auto_research] tavily fail: {e}", file=sys.stderr)
        return []


def _synthesize_with_brain(query: str, results: list[dict]) -> str:
    """Pide al brain que sintetice los hallazgos en 4-6 lineas accionables."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
    except ImportError:
        return "(brain unavailable - sin sintesis)"
    if not results:
        prompt = (
            f"PREGUNTA: {query}\n\nNo se encontraron resultados web. "
            "Razona con tu conocimiento propio. Devuelve 4-6 lineas con "
            "alternativas concretas accionables hoy 2026, costos estimados, "
            "y nivel de dificultad. Espanol."
        )
    else:
        bullets = "\n".join(
            f"- {r['title']}: {r['snippet']} [{r['url']}]"
            for r in results[:8])
        prompt = (
            f"PREGUNTA: {query}\n\nRESULTADOS WEB:\n{bullets}\n\n"
            "Sintetiza en 4-6 lineas: que alternativas concretas existen, "
            "costo estimado USD, cual es la mas pragmatica para una startup "
            "1-persona LATAM, y por que. Espanol, sin disclaimers."
        )
    out = ask_claude(
        prompt,
        system=("Eres analista de research. Conciso, accionable, sin fluff. "
                "Cita el URL relevante en cada claim si esta disponible."),
        max_tokens=600,
    )
    return out or "(brain returned None)"


def deep_research(query: str, max_results: int = 8) -> dict:
    """Cascade: Tavily > Brave > DDG Lite > brain only."""
    start = time.time()
    source = "none"
    results: list[dict] = []

    for fn_name, fn in [("tavily", _tavily_search),
                         ("brave", _brave_search),
                         ("ddg_lite", _ddg_lite)]:
        try:
            results = fn(query, limit=max_results)
        except Exception:
            results = []
        if results:
            source = fn_name
            break

    synthesis = _synthesize_with_brain(query, results)
    elapsed = int((time.time() - start) * 1000)
    return {
        "query": query,
        "source": source,
        "results_count": len(results),
        "results": results,
        "synthesis": synthesis,
        "elapsed_ms": elapsed,
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("query", help="Query a investigar")
    p.add_argument("--limit", type=int, default=8)
    args = p.parse_args()
    r = deep_research(args.query, max_results=args.limit)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
