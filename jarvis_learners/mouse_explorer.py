"""mouse_explorer.py — Exploración ACTIVA del entorno.

Jarvis usa el mouse para DESCUBRIR qué hay y qué puede hacer.
NO mira tutoriales. TOCA, ve qué pasa, registra.

Filosofia (curiosity-driven exploration):
  1. Screenshot estado actual
  2. Detecta elementos clickables (botones, links, menus)
  3. Para cada elemento:
     a. Hover → screenshot → comparar (¿aparece tooltip?)
     b. Click → screenshot → comparar (¿cambia algo?)
     c. Registra: "click en X causa Y"
  4. Construye MAPA EMPIRICO del sistema/app/web
  5. Repite con elementos descubiertos (BFS)

Modos:
  - web:     explora un sitio web con Playwright (SEGURO en host)
  - desktop: explora desktop Windows (REQUIERE sandbox VM)
  - app:     explora una app específica (REQUIERE sandbox VM)

Empezamos con `web` que es seguro y demuestra el concepto.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

DISCOVERY_DIR = ROOT / "data" / "discoveries"


def log(msg: str):
    print(f"[mouse_explorer {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ============================================================================
# MODO WEB — Playwright explora sitio (seguro, no toca OS)
# ============================================================================
async def explore_web_site(url: str, max_steps: int = 15) -> dict:
    """Visita URL, descubre elementos clickables, hovers, registra qué hace cada uno.

    Output: knowledge graph del sitio: {url, elements: [{selector, text, action, result}]}
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return {"error": "playwright no instalado"}

    DISCOVERY_DIR.mkdir(parents=True, exist_ok=True)
    safe_url = url.replace("https://", "").replace("/", "_")[:50]
    out_dir = DISCOVERY_DIR / f"web_{safe_url}_{int(time.time())}"
    out_dir.mkdir(parents=True)

    discoveries = []
    log(f"=== EXPLORANDO {url} (max {max_steps} interacciones) ===")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await ctx.new_page()

        # Step 0: cargar página
        log(f"  goto {url}")
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.screenshot(path=str(out_dir / "step_00_initial.png"))
        except Exception as e:
            await browser.close()
            return {"error": f"goto fallo: {e}"}

        # Step 1: descubrir TODOS los elementos clickables
        log("  inspeccionando elementos clickables...")
        clickables = await page.evaluate("""
            () => {
                const sels = ['a', 'button', 'input[type=button]', 'input[type=submit]',
                              '[role=button]', '[onclick]'];
                const found = [];
                for (const sel of sels) {
                    const elements = document.querySelectorAll(sel);
                    for (let i = 0; i < Math.min(elements.length, 30); i++) {
                        const el = elements[i];
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < 720) {
                            found.push({
                                tag: el.tagName.toLowerCase(),
                                text: (el.textContent || el.value || '').trim().slice(0, 60),
                                href: el.href || null,
                                x: Math.round(rect.x + rect.width/2),
                                y: Math.round(rect.y + rect.height/2),
                                w: Math.round(rect.width),
                                h: Math.round(rect.height),
                            });
                        }
                    }
                }
                return found;
            }
        """)
        log(f"  {len(clickables)} elementos clickables encontrados (visible viewport)")

        # Step 2: hover cada elemento para ver tooltips
        for i, el in enumerate(clickables[:max_steps]):
            try:
                log(f"  [{i+1}/{min(len(clickables), max_steps)}] hover '{el['text'][:40]}'")
                await page.mouse.move(el["x"], el["y"])
                await asyncio.sleep(0.5)
                # Capturar título/tooltip si aparece
                title = await page.evaluate(
                    "(coords) => document.elementFromPoint(coords.x, coords.y)?.title || ''",
                    {"x": el["x"], "y": el["y"]},
                )
                discoveries.append({
                    "step": i + 1,
                    "action": "hover",
                    "element": el,
                    "tooltip": title,
                })
            except Exception as e:
                log(f"  hover fallo: {e}")

        # Step 3: screenshot final con mapa de elementos
        await page.screenshot(path=str(out_dir / "step_99_final.png"))

        # Guardar discoveries
        knowledge = {
            "url": url,
            "explored_at": datetime.now().isoformat(),
            "viewport": {"w": 1280, "h": 720},
            "clickable_elements_found": len(clickables),
            "interactions_done": len(discoveries),
            "discoveries": discoveries,
            "out_dir": str(out_dir),
        }
        (out_dir / "knowledge.json").write_text(
            json.dumps(knowledge, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        await browser.close()
        log(f"OK explorado. Knowledge en {out_dir}/knowledge.json")
        return knowledge


# ============================================================================
# MODO DESKTOP — usa UIA tree (REQUIERE sandbox VM)
# ============================================================================
async def explore_desktop(safety_check: bool = True) -> dict:
    """Explora desktop Windows usando UIA tree. CADA elemento clickable, hover, lee labels.

    REQUIERE sandbox VM o JARVIS_FORCE_HOST=1 explícito (peligroso en host).
    """
    import os, socket
    if safety_check:
        host = socket.gethostname().lower()
        user = (os.environ.get("USERNAME") or "").lower()
        in_sandbox = "wdagutilityaccount" in user or "wdagutilityaccount" in host
        force = os.environ.get("JARVIS_FORCE_HOST") == "1"
        if not in_sandbox and not force:
            return {"error": "desktop exploration BLOCKED: no estas en sandbox VM. Setea JARVIS_FORCE_HOST=1 si SABES lo que haces"}

    try:
        import pyautogui
        import pywinauto
    except ImportError:
        return {"error": "pyautogui/pywinauto no instalados"}

    log("=== EXPLORANDO DESKTOP (UIA tree) ===")
    discoveries = []
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        log(f"  {len(windows)} ventanas abiertas detectadas")
        for w in windows[:5]:
            try:
                title = w.window_text()
                rect = w.rectangle()
                discoveries.append({
                    "type": "window", "title": title,
                    "bounds": [rect.left, rect.top, rect.right, rect.bottom],
                })
            except Exception:
                continue
    except Exception as e:
        return {"error": str(e)}

    return {"discoveries": discoveries, "mode": "desktop_uia"}


# ============================================================================
# CLI
# ============================================================================
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python mouse_explorer.py web <url>")
        print("  python mouse_explorer.py desktop")
        sys.exit(1)
    mode = sys.argv[1]
    if mode == "web":
        url = sys.argv[2] if len(sys.argv) > 2 else "https://www.google.com"
        result = asyncio.run(explore_web_site(url, max_steps=12))
    elif mode == "desktop":
        result = asyncio.run(explore_desktop())
    else:
        print(f"modo desconocido: {mode}")
        sys.exit(1)
    print(json.dumps({
        "mode": mode,
        "summary": {
            "url": result.get("url"),
            "clickables": result.get("clickable_elements_found"),
            "interactions": result.get("interactions_done"),
            "errors": result.get("error"),
        }
    }, ensure_ascii=False, indent=2))
