"""stealth_browser.py - Playwright con evasion anti-bot moderna.

playwright-stealth + Bezier mouse + UA rotation + viewport jitter.
Usado para research legitimo (docs, sitios publicos) donde el bot
detection genera falsos positivos contra requests automatizados.

NO destinado a DM masivo en redes sociales — los modelos 2026 de Meta/X
detectan patrones de bot incluso con stealth perfecto. Ese mercado
requiere servicios residenciales ($500+/mes) y aun asi tienen 40-50%
ban rate. Honesto.

Uso legitimo:
  - Scrape docs.stripe.com sin bloqueos de Cloudflare
  - Research de competidores en sitios protegidos
  - Llenar formularios publicos B2B (Calendly, Typeform)
  - Tests E2E contra sitios con anti-bot Akamai

API:
  with stealth_session() as page:
      page.goto(...)
      bezier_click(page, x, y)
      humanlike_type(page, selector, text)
"""
from __future__ import annotations

import math
import random
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1366, "height": 768},
]


def _try_stealth(page) -> bool:
    """Intenta aplicar playwright-stealth si esta instalado."""
    try:
        from playwright_stealth import stealth_sync
        stealth_sync(page)
        return True
    except ImportError:
        # Fallback: inyectar JS basico anti-deteccion sin librery
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {name: 'PDF Viewer', filename: 'internal-pdf-viewer'},
                    {name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer'},
                    {name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer'},
                ]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['es-MX', 'es', 'en-US', 'en']
            });
            window.chrome = {runtime: {}};
            // WebGL spoof basico
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(param) {
                if (param === 37445) return 'Intel Inc.';
                if (param === 37446) return 'Intel(R) Iris(R) Plus Graphics';
                return getParameter.apply(this, arguments);
            };
        """)
        return False


@contextmanager
def stealth_session(headless: bool = True,
                     locale: str = "es-MX") -> Iterator:
    """Context manager: lanza Chromium stealth + cleanup.

    Returns: (browser, context, page) — caller usa el page.
    """
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    browser = None
    try:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
            ],
        )
        ctx = browser.new_context(
            user_agent=random.choice(UA_POOL),
            viewport=random.choice(VIEWPORTS),
            locale=locale,
            timezone_id="America/Mexico_City",
            permissions=["geolocation"],
            geolocation={"latitude": 20.5888, "longitude": -100.3899},  # QRO
        )
        page = ctx.new_page()
        applied = _try_stealth(page)
        page.set_extra_http_headers({
            "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
            "Sec-Ch-Ua": '"Not_A Brand";v="99", "Chromium";v="121", "Google Chrome";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
        })
        page._stealth_applied = applied  # type: ignore
        yield page
    finally:
        try:
            if browser:
                browser.close()
        except Exception:
            pass
        p.stop()


def _bezier_points(x0: int, y0: int, x1: int, y1: int,
                    steps: int = 30) -> list[tuple[float, float]]:
    """Genera N puntos de una curva Bezier cubica con control aleatorio."""
    cx1 = x0 + (x1 - x0) * random.uniform(0.2, 0.5) + random.randint(-50, 50)
    cy1 = y0 + (y1 - y0) * random.uniform(0.2, 0.5) + random.randint(-50, 50)
    cx2 = x0 + (x1 - x0) * random.uniform(0.5, 0.8) + random.randint(-50, 50)
    cy2 = y0 + (y1 - y0) * random.uniform(0.5, 0.8) + random.randint(-50, 50)
    pts = []
    for i in range(steps + 1):
        t = i / steps
        b = (1 - t) ** 3
        c = 3 * (1 - t) ** 2 * t
        d = 3 * (1 - t) * t ** 2
        e = t ** 3
        x = b * x0 + c * cx1 + d * cx2 + e * x1
        y = b * y0 + c * cy1 + d * cy2 + e * y1
        pts.append((x, y))
    return pts


def bezier_move(page, target_x: int, target_y: int) -> None:
    """Mueve mouse con curva Bezier + jitter velocidad."""
    try:
        start = page.evaluate("() => ({x: window._lastMouse?.x || 0, y: window._lastMouse?.y || 0})")
        x0 = int(start.get("x", random.randint(100, 800)))
        y0 = int(start.get("y", random.randint(100, 600)))
    except Exception:
        x0, y0 = random.randint(100, 800), random.randint(100, 600)
    steps = random.randint(20, 40)
    pts = _bezier_points(x0, y0, target_x, target_y, steps)
    for x, y in pts:
        try:
            page.mouse.move(x, y, steps=1)
        except Exception:
            pass
        # Pausa irregular entre 8-30ms
        time.sleep(random.uniform(0.008, 0.030))
    try:
        page.evaluate(
            "(p) => { window._lastMouse = {x: p.x, y: p.y}; }",
            {"x": target_x, "y": target_y},
        )
    except Exception:
        pass


def bezier_click(page, target_x: int, target_y: int) -> None:
    bezier_move(page, target_x, target_y)
    time.sleep(random.uniform(0.05, 0.2))  # pausa pre-click humana
    page.mouse.down()
    time.sleep(random.uniform(0.04, 0.12))
    page.mouse.up()


def humanlike_type(page, text: str, *, jitter_ms_min: int = 50,
                    jitter_ms_max: int = 180,
                    typo_rate: float = 0.02) -> None:
    """Escribe con timing humano + posibles typos auto-corregidos."""
    for ch in text:
        # Typo aleatorio: escribe char incorrecto, espera, borra, escribe correcto
        if random.random() < typo_rate and ch.isalpha():
            wrong = random.choice("qwertyuiopasdfghjklzxcvbnm")
            page.keyboard.type(wrong)
            time.sleep(random.uniform(0.15, 0.4))
            page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.08, 0.2))
        page.keyboard.type(ch)
        time.sleep(random.uniform(jitter_ms_min, jitter_ms_max) / 1000.0)
        # Pausa irregular en espacios o signos (mas humano)
        if ch in " .,!?\n":
            time.sleep(random.uniform(0.1, 0.4))


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://bot.sannysoft.com",
                        help="URL test (default: bot detection test page)")
    args = parser.parse_args()
    with stealth_session(headless=True) as page:
        page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        title = page.title()
        body_text = page.evaluate("() => document.body.innerText")[:600]
        stealth_active = getattr(page, "_stealth_applied", False)
        print(f"URL: {args.url}")
        print(f"Title: {title}")
        print(f"playwright-stealth applied: {stealth_active}")
        print(f"Body head:\n{body_text}")
