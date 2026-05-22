"""gemini_web_chat.py - Habla con Gemini Pro via web (browser_cdp).

Aprovecha la suscripcion Gemini Pro logueada en tu Brave (cookies) en lugar
de consumir cuota API. Para tareas pesadas, cambia automaticamente al modelo
'2.5 Pro Thinking' (razonamiento profundo) usando el selector del UI.

NO requiere API key. NO consume quota. Lento (15-30s por respuesta).

Uso:
    from jarvis_v2.skills.gemini_web_chat import ask_gemini_web
    resp = ask_gemini_web("Analiza este trade...", use_thinking=True)
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GEMINI_URL = "https://gemini.google.com/app"


def _find_gemini_page(ctx):
    """Busca pestana Gemini existente o abre nueva."""
    for pg in ctx.pages:
        try:
            if "gemini.google.com" in pg.url:
                return pg
        except Exception:
            continue
    pg = ctx.new_page()
    pg.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4)
    return pg


def _switch_to_thinking(page) -> bool:
    """Toggle a modelo '2.5 Pro' / Thinking. Heuristica DOM + texto."""
    try:
        # 1. Click selector de modelo (top-left, suele decir "2.5 Flash" o "2.5 Pro")
        selectors = [
            "button[aria-label*='model']",
            "[data-test-id='model-selector']",
            "button:has-text('Flash')",
            "button:has-text('2.5')",
            "div[role='button']:has-text('Flash')",
        ]
        clicked = False
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=2000):
                    el.click(timeout=3000)
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            print("[gemini_web] no encontre selector modelo", file=sys.stderr)
            return False
        time.sleep(1)

        # 2. Click en opcion 'Pro' o 'Thinking'
        for opt_text in ("Pro", "Thinking", "2.5 Pro", "Razonamiento"):
            try:
                opt = page.locator(f"text={opt_text}").first
                if opt.is_visible(timeout=2000):
                    opt.click(timeout=3000)
                    time.sleep(1)
                    return True
            except Exception:
                continue
        return False
    except Exception as e:
        print(f"[gemini_web] switch model fail: {e}", file=sys.stderr)
        return False


def ask_gemini_web(prompt: str, use_thinking: bool = False,
                    timeout_response_s: int = 90) -> dict:
    """Manda prompt a Gemini Pro Web via tu Brave. Devuelve {ok, text, model}.

    Args:
        prompt: el mensaje al modelo.
        use_thinking: True -> intenta cambiar a 2.5 Pro Thinking.
        timeout_response_s: cuanto esperar a que Gemini termine.
    """
    try:
        from jarvis_v2.skills import browser_cdp
    except ImportError as e:
        return {"ok": False, "error": f"browser_cdp no disponible: {e}"}

    p, browser, ctx, page = browser_cdp.attach()
    try:
        page = _find_gemini_page(ctx)
        page.bring_to_front()
        time.sleep(2)

        if use_thinking:
            switched = _switch_to_thinking(page)
            print(f"[gemini_web] thinking mode: {'OK' if switched else 'FAIL (sigue flash)'}",
                  file=sys.stderr)

        # 3. Localizar input (Gemini usa rich-editable div, no <textarea>)
        input_selectors = [
            "rich-textarea div[contenteditable='true']",
            "div[contenteditable='true'][aria-label*='prompt']",
            "div[contenteditable='true'][role='textbox']",
            "textarea",
        ]
        input_el = None
        for sel in input_selectors:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=3000):
                    input_el = el
                    break
            except Exception:
                continue
        if not input_el:
            return {"ok": False, "error": "no input encontrado en Gemini UI"}

        input_el.click()
        time.sleep(0.5)
        # Tipea con keyboard (Gemini contenteditable a veces ignora .fill)
        page.keyboard.type(prompt, delay=10)
        time.sleep(0.8)

        # 4. Click send (Enter o boton send)
        try:
            send_btn = page.locator("button[aria-label*='Send'], button[aria-label*='Enviar']").first
            if send_btn.is_visible(timeout=2000):
                send_btn.click()
            else:
                page.keyboard.press("Enter")
        except Exception:
            page.keyboard.press("Enter")

        # 5. Esperar respuesta (Gemini muestra spinner mientras genera)
        time.sleep(3)
        start = time.time()
        last_text = ""
        stable_count = 0
        while time.time() - start < timeout_response_s:
            # Get last message response
            try:
                msgs = page.locator("message-content, .model-response-text, [data-message-type='response']").all()
                if msgs:
                    cur = msgs[-1].inner_text(timeout=2000)
                    if cur == last_text and len(cur) > 20:
                        stable_count += 1
                        if stable_count >= 3:  # 3 polls iguales = terminó
                            break
                    else:
                        last_text = cur
                        stable_count = 0
            except Exception:
                pass
            time.sleep(2)

        if not last_text:
            # Fallback: lee TODO el body y devuelve la cola
            body_txt = page.evaluate("() => document.body.innerText")
            last_text = body_txt[-3000:] if body_txt else ""

        model_label = "2.5-pro-thinking" if use_thinking else "2.5-flash"
        return {"ok": True, "text": last_text.strip(),
                "model": model_label,
                "duration_s": round(time.time() - start, 1)}
    finally:
        p.stop()


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else (
        "En 2 lineas: que es Jarvis V2?"
    )
    use_thinking = "--thinking" in sys.argv
    r = ask_gemini_web(prompt, use_thinking=use_thinking)
    import json
    print(json.dumps(r, ensure_ascii=False, indent=2)[:2000])
