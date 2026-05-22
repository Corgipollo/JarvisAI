"""browser_cdp.py - Conecta a Brave/Chrome existente via Chrome DevTools Protocol.

Estrategia "Hijack" (Gemini consejo): NO lanzar Chromium nuevo (1 GB RAM extra).
En su lugar, conectar al navegador del usuario que YA esta corriendo con
--remote-debugging-port=9222. Asi heredamos sus cookies/sessions (Twitter,
Reddit, Gmail, etc.).

Setup del navegador (UNA vez):
  Brave/Chrome shortcut -> Target: "...brave.exe" --remote-debugging-port=9222

API:
  attach() -> Playwright Browser conectado
  find_element_coords(page, selector) -> (x, y) absolutos en pantalla
  navigate(page, url)
  click_humanly(page, selector) - combina DOM lookup + human_mouse Bezier
  type_humanly(page, selector, text)
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CDP_URL = "http://127.0.0.1:9222"


def attach(cdp_url: str = CDP_URL):
    """Devuelve (playwright, browser, context, page).
    El page es la primera pestaña del navegador existente.
    Caller debe llamar browser.close() = NO, eso cerraria el browser del usuario.
    Simplemente dejar de usar; Playwright se desconecta al GC.
    """
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    try:
        browser = p.chromium.connect_over_cdp(cdp_url)
    except Exception as e:
        p.stop()
        raise RuntimeError(
            f"No se pudo conectar al navegador en {cdp_url}. "
            f"Asegurate que Brave/Chrome esta abierto con "
            f"--remote-debugging-port=9222. Error: {e}"
        )
    contexts = browser.contexts
    if not contexts:
        raise RuntimeError("Navegador sin contexts. Abre al menos una pestana.")
    ctx = contexts[0]
    pages = ctx.pages
    page = pages[0] if pages else ctx.new_page()
    return p, browser, ctx, page


def find_element_coords(page, selector: str) -> tuple[int, int] | None:
    """Locator -> getBoundingClientRect -> coords absolutos en pantalla.
    Suma offset de la ventana del browser y la barra de URL/tabs."""
    try:
        loc = page.locator(selector).first
        box = loc.bounding_box(timeout=5000)
        if not box:
            return None
        center_x_rel = box["x"] + box["width"] / 2
        center_y_rel = box["y"] + box["height"] / 2
        # Window position absoluto via JS
        offset = page.evaluate("""() => ({
            x: window.screenX || window.screenLeft || 0,
            y: window.screenY || window.screenTop || 0,
            chrome_y: window.outerHeight - window.innerHeight
        })""")
        abs_x = int(offset["x"] + center_x_rel)
        abs_y = int(offset["y"] + offset["chrome_y"] + center_y_rel)
        return (abs_x, abs_y)
    except Exception as e:
        print(f"[browser_cdp] find_element_coords fail: {e}", file=sys.stderr)
        return None


def navigate(page, url: str, wait_until: str = "domcontentloaded"):
    """Navega la pagina actual al URL dado."""
    return page.goto(url, wait_until=wait_until, timeout=30000)


def click_humanly(page, selector: str) -> dict:
    """Combina: 1) localiza elemento via DOM, 2) coords absolutos,
    3) human_mouse.human_click con curva Bezier."""
    coords = find_element_coords(page, selector)
    if not coords:
        return {"ok": False, "error": f"selector_not_found: {selector}"}
    x, y = coords
    try:
        from jarvis_v2.swarm.human_mouse import human_click
        human_click(x, y)
        return {"ok": True, "coords": (x, y)}
    except Exception as e:
        return {"ok": False, "error": f"human_click_fail: {e}"}


def type_humanly(page, selector: str, text: str) -> dict:
    """Click humano + tipo human-paced via pyautogui human_type."""
    r = click_humanly(page, selector)
    if not r.get("ok"):
        return r
    try:
        import time
        from jarvis_v2.swarm.human_mouse import human_type
        time.sleep(0.4)
        human_type(text, base_wpm=70)
        return {"ok": True, "typed": text[:60]}
    except Exception as e:
        return {"ok": False, "error": f"human_type_fail: {e}"}


def find_text_on_page(page, text: str) -> bool:
    """Verifica si un texto esta visible en la pagina (post-action verifier)."""
    try:
        return page.locator(f"text={text}").first.is_visible(timeout=3000)
    except Exception:
        return False


if __name__ == "__main__":
    # Smoke test: connecta + reporta pestanas abiertas
    try:
        p, browser, ctx, page = attach()
        print(f"OK: conectado a {CDP_URL}")
        print(f"  URL actual: {page.url}")
        print(f"  Titulo: {page.title()}")
        print(f"  Contexts: {len(browser.contexts)}, pages: {len(ctx.pages)}")
        p.stop()
    except Exception as e:
        print(f"FAIL: {e}")
        print("Para arrancar Brave con CDP:")
        print('  "C:\\Program Files\\BraveSoftware\\Brave-Browser\\Application\\brave.exe" --remote-debugging-port=9222')
