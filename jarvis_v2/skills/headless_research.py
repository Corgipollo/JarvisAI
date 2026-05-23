"""headless_research.py - Clon Fantasma: navegador invisible para el agente.

Diferencia critica vs browser_cdp.py:
  - browser_cdp.py: ATTACH al Brave del usuario (comparte cookies, RIESGO de
    interferir con su navegacion activa).
  - headless_research.py: LAUNCH Chromium propio en modo headless (invisible,
    aislado, sin interferir, sin secuestrar mouse).

Casos de uso:
  - Leer documentacion externa (Stripe, AutoDS, Shopify dev docs) sin tocar
    el navegador del usuario.
  - Hacer research silencioso para alimentar al planner sin GUI interruption.
  - Smoke tests E2E contra URLs publicas.

API:
    fetch_text(url) -> str            # navega + return innerText body
    fetch_with_query(url, css_selector) -> list[str]  # texto de matches
    smart_search(query) -> list[dict] # DuckDuckGo HTML SERP scraping

NO requiere Brave abierto. NO toca el mouse fisico. Costo: ~200MB RAM por
sesion (browser fantasma vive en memoria).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _launch_headless():
    """Lanza Chromium headless aislado. Caller responsable de close()."""
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        browser = p.chromium.launch(headless=True, args=[
            "--disable-gpu",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ])
    except Exception as e:
        p.stop()
        raise RuntimeError(f"chromium launch failed: {e}. "
                            "Try: playwright install chromium")
    ctx = browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) "
                     "Chrome/120.0.0.0 Safari/537.36"),
    )
    return p, browser, ctx


def fetch_text(url: str, wait_ms: int = 1500, max_chars: int = 50000) -> str:
    """Navega a URL, espera DOM, devuelve innerText del body.

    Args:
        url: URL absoluta.
        wait_ms: espera adicional tras domcontentloaded (para SPAs).
        max_chars: trim del texto (evita reventar contexto LLM).
    """
    p, browser, ctx = _launch_headless()
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(wait_ms)
        text = page.evaluate("() => document.body.innerText")
        return (text or "")[:max_chars]
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()


def fetch_with_query(url: str, css_selector: str,
                       wait_ms: int = 1500) -> list[str]:
    """Navega + devuelve innerText de cada match del selector CSS."""
    p, browser, ctx = _launch_headless()
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(wait_ms)
        elements = page.query_selector_all(css_selector)
        return [(el.inner_text() or "").strip()
                for el in elements if el.inner_text()]
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()


def smart_search(query: str, top_n: int = 8) -> list[dict]:
    """Busqueda DuckDuckGo HTML (no requiere API key). Devuelve title+url+snippet."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    p, browser, ctx = _launch_headless()
    try:
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(800)
        results = page.evaluate("""
            () => {
                const items = document.querySelectorAll('.result');
                return Array.from(items).slice(0, 20).map(r => ({
                    title: (r.querySelector('.result__title')?.innerText || '').trim(),
                    url: r.querySelector('.result__a')?.href || '',
                    snippet: (r.querySelector('.result__snippet')?.innerText || '').trim(),
                }));
            }
        """)
        return [r for r in (results or []) if r["title"]][:top_n]
    finally:
        try:
            browser.close()
        except Exception:
            pass
        p.stop()


if __name__ == "__main__":
    import argparse
    import json
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="URL a fetch")
    parser.add_argument("--search", help="Query para DuckDuckGo SERP")
    parser.add_argument("--selector", help="CSS selector para fetch_with_query")
    args = parser.parse_args()

    if args.search:
        out = smart_search(args.search)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.url and args.selector:
        out = fetch_with_query(args.url, args.selector)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.url:
        out = fetch_text(args.url)
        print(out[:3000])
    else:
        print("Usage: --url URL [--selector CSS] | --search QUERY")
