"""browser.py — Browser automation con Playwright.

Async wrapper que mantiene browser/page stateful para que Jarvis pueda
navegar paginas, llenar forms, hacer scraping rapido.

Uso:
    from backend.skills.browser import Browser
    async with Browser() as b:
        await b.goto("https://gmail.com")
        await b.click_text("Compose")
        await b.type_into("textarea[name='to']", "alejandro@x.com")
        text = await b.read_text()
"""
from __future__ import annotations

from typing import Optional

try:
    from playwright.async_api import async_playwright, Page, Browser as PWBrowser
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


class Browser:
    def __init__(self, headless: bool = False, channel: str = "chrome"):
        self.headless = headless
        self.channel = channel
        self._pw = None
        self._browser: Optional["PWBrowser"] = None
        self._page: Optional["Page"] = None

    async def __aenter__(self):
        if not HAS_PLAYWRIGHT:
            raise RuntimeError("playwright no instalado: pip install playwright && playwright install")
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self.headless, channel=self.channel)
        ctx = await self._browser.new_context()
        self._page = await ctx.new_page()
        return self

    async def __aexit__(self, *exc):
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    async def goto(self, url: str) -> dict:
        try:
            await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return {"success": True, "url": self._page.url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click(self, selector: str) -> dict:
        try:
            await self._page.click(selector, timeout=10000)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def click_text(self, text: str) -> dict:
        try:
            await self._page.get_by_text(text).first.click(timeout=10000)
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def type_into(self, selector: str, text: str) -> dict:
        try:
            await self._page.fill(selector, text, timeout=10000)
            return {"success": True, "selector": selector, "chars": len(text)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def read_text(self, selector: str = "body") -> dict:
        try:
            text = await self._page.text_content(selector)
            return {"success": True, "text": text or "", "chars": len(text or "")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def screenshot(self, path: str) -> dict:
        try:
            await self._page.screenshot(path=path, full_page=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def evaluate(self, js: str) -> dict:
        try:
            result = await self._page.evaluate(js)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def quick_search(query: str, engine: str = "duckduckgo") -> dict:
    """Atajo: busca en DDG/Google y devuelve top results titulos+urls."""
    urls = {
        "duckduckgo": f"https://duckduckgo.com/?q={query}",
        "google": f"https://www.google.com/search?q={query}",
    }
    url = urls.get(engine, urls["duckduckgo"])
    async with Browser(headless=True) as b:
        r = await b.goto(url)
        if not r["success"]:
            return r
        # Extraer titulos top 5 (DDG)
        results = await b.evaluate("""
            Array.from(document.querySelectorAll('article h2 a, .result__title a')).slice(0, 5)
                 .map(a => ({title: a.textContent.trim(), url: a.href}))
        """)
        return {"success": True, "query": query, "results": results.get("result", [])}
