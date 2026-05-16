"""deep_research.py - Investigacion web robusta.

3 tiers:
  1. crawl4ai (LLM-friendly extraction, JS-rendered)
  2. duckduckgo-search + requests + BeautifulSoup
  3. requests raw (ultimo recurso)

Output: summary + raw_chunks + sources. Guarda en Mem para no reinvestigar.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DEEP_CACHE = ROOT / "data" / "deep_research_cache"
DEEP_CACHE.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _cache_key(query: str) -> str:
    return hashlib.sha256(query.lower().encode()).hexdigest()[:16]


def _read_cache(query: str, ttl_hours: int = 24) -> dict | None:
    p = DEEP_CACHE / f"{_cache_key(query)}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ts = datetime.fromisoformat(data.get("ts", "1970-01-01"))
        if datetime.utcnow() - ts > timedelta(hours=ttl_hours):
            return None
        return data
    except Exception:
        return None


def _write_cache(query: str, data: dict):
    p = DEEP_CACHE / f"{_cache_key(query)}.json"
    data["ts"] = datetime.utcnow().isoformat()
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, default=str),
                     encoding="utf-8")
    except Exception:
        pass


def web_search(query: str, max_results: int = 8) -> list[dict]:
    """DuckDuckGo Lite search. Returns [{title, url, snippet}]."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results,
                                      region="wt-wt", safesearch="off"))
            return [{"title": r.get("title", ""),
                     "url": r.get("href", ""),
                     "snippet": r.get("body", "")[:300]}
                    for r in results]
    except Exception as e:
        print(f"[research] ddgs failed: {e}", flush=True)
        return []


def fetch_url(url: str, timeout: int = 15) -> str | None:
    """Tier 2: requests + bs4. Limpia HTML, devuelve texto."""
    if not url or not url.startswith(("http://", "https://")):
        return None
    try:
        r = requests.get(url, headers={"User-Agent": UA},
                         timeout=timeout, allow_redirects=True)
        if r.status_code != 200:
            return None
        ct = r.headers.get("content-type", "")
        if "text/html" not in ct and "application/xhtml" not in ct:
            return None
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "html.parser")
        # Remove scripts, styles, nav, footer
        for tag in soup(["script", "style", "nav", "footer", "header",
                          "aside", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:20000]  # cap content
    except Exception as e:
        print(f"[research] fetch_url {url[:50]} failed: {e}", flush=True)
        return None


def crawl4ai_fetch(url: str) -> str | None:
    """Tier 1: crawl4ai. Solo si crawl4ai esta instalado correctamente."""
    try:
        # crawl4ai requires AsyncWebCrawler; sync wrapper
        import asyncio
        from crawl4ai import AsyncWebCrawler

        async def _run():
            async with AsyncWebCrawler(verbose=False) as crawler:
                result = await crawler.arun(url=url)
                return result.markdown if result.success else None

        return asyncio.run(_run())
    except Exception as e:
        print(f"[research] crawl4ai failed for {url[:50]}: {e}", flush=True)
        return None


def deep_research(query: str, max_sources: int = 5,
                   use_cache: bool = True, save_to_mem: bool = True) -> dict:
    """Investigacion completa. Search -> fetch top sources -> summary.

    Returns:
        {
            "query": str,
            "ts": iso,
            "sources": [{title, url, content_chars}],
            "raw_chunks": [str, ...],  # textos crudos
            "cached": bool,
        }
    """
    if use_cache:
        cached = _read_cache(query)
        if cached:
            print(f"[research] cache hit for '{query[:40]}'", flush=True)
            cached["cached"] = True
            return cached

    print(f"[research] searching: '{query}'", flush=True)
    results = web_search(query, max_results=max_sources * 2)
    if not results:
        return {"query": query, "sources": [], "raw_chunks": [],
                "cached": False, "error": "no_search_results"}

    sources = []
    chunks = []
    for r in results[:max_sources]:
        url = r.get("url", "")
        if not url:
            continue
        # Tier 1 first (crawl4ai), tier 2 fallback (requests+bs4)
        content = crawl4ai_fetch(url) or fetch_url(url)
        if not content:
            continue
        sources.append({
            "title": r.get("title", ""),
            "url": url,
            "snippet": r.get("snippet", ""),
            "content_chars": len(content),
        })
        chunks.append(f"--- {r.get('title', '')[:80]} ---\nURL: {url}\n\n{content[:5000]}")
        time.sleep(0.5)  # polite

    payload = {
        "query": query,
        "ts": datetime.utcnow().isoformat(),
        "sources": sources,
        "raw_chunks": chunks,
        "cached": False,
    }
    if use_cache:
        _write_cache(query, payload)

    if save_to_mem and chunks:
        try:
            from jarvis_v2.memory.memory_manager import save_lesson
            insight = (
                f"Research realizado sobre '{query}'. "
                f"{len(sources)} fuentes encontradas. "
                f"Topicos cubiertos: {', '.join(s['title'][:50] for s in sources[:3])}"
            )
            save_lesson(
                insight=insight,
                tags=["research", "topic_known"] + query.lower().split()[:3],
                context=f"deep_research call ts={payload['ts']}",
                severity="low",
            )
        except Exception as e:
            print(f"[research] mem save fail: {e}", flush=True)

    return payload


def summarize(research_payload: dict, focus: str = "") -> str:
    """Resume hallazgos via Claude. Focus = pregunta especifica."""
    try:
        from jarvis_bridge.jarvis_brain import ask_claude
    except ImportError:
        return "(jarvis_brain no disponible)"

    sources = research_payload.get("sources", [])
    chunks = research_payload.get("raw_chunks", [])
    if not chunks:
        return "(no hay contenido para resumir)"

    combined = "\n\n".join(chunks)[:30000]
    prompt = (
        f"Query original: {research_payload.get('query', '')}\n"
        f"Focus: {focus or 'resumen general'}\n\n"
        f"FUENTES ({len(sources)}):\n{combined}\n\n"
        "Genera un resumen ejecutivo en 5-8 bullets. Identifica:\n"
        "- Tendencias clave\n- Oportunidades comerciales viables\n"
        "- Riesgos/barreras\n- Stack tecnico requerido"
    )
    return ask_claude(prompt, model="claude-sonnet-4-6", max_tokens=1500) or ""


if __name__ == "__main__":
    import sys
    q = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "nichos de bots de Discord rentables 2026"
    )
    res = deep_research(q, max_sources=3)
    print(f"\n=== Found {len(res['sources'])} sources ===")
    for s in res["sources"]:
        print(f"  - {s['title'][:80]} ({s['content_chars']} chars)")
    print("\n=== Summary ===")
    print(summarize(res, focus="oportunidades viables con budget <$100")[:2000])
