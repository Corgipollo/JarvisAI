"""telegram_desktop_setup.py - Auto-saca el token de Telegram via la app
Telegram Desktop nativa que Emmanuel YA tiene logueada en Windows.

Usa desktop_hybrid (OCR + cv2) + human_mouse + pyautogui.write para
controlar la app nativa SIN browser.

Flujo:
  1. Abre Telegram Desktop (Win+R "Telegram" o por path conocido)
  2. desktop_scan -> busca caja de search visible
  3. Click search, tipea "BotFather", Enter
  4. Click resultado BotFather
  5. Tipea /newbot, Enter, espera respuesta
  6. Tipea nombre, Enter
  7. Tipea username (con variantes si tomado), Enter
  8. Espera token, lo extrae del area de mensajes via OCR
  9. Guarda en .env + setx
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


TG_DESKTOP_PATHS = [
    r"C:\Users\Emmanuel\AppData\Roaming\Telegram Desktop\Telegram.exe",
    r"C:\Program Files\Telegram Desktop\Telegram.exe",
    r"C:\Program Files (x86)\Telegram Desktop\Telegram.exe",
]


def _open_telegram_app() -> bool:
    """Abre + maximize + foreground Telegram Desktop (clave para OCR)."""
    import pygetwindow as gw
    wins = gw.getWindowsWithTitle("Telegram")
    if wins:
        w = wins[0]
        try:
            if w.isMinimized:
                w.restore()
            try:
                w.maximize()
            except Exception:
                pass
            w.activate()
            time.sleep(1)
            # Force foreground via Win32 API por si activate falla
            try:
                import ctypes
                hwnd = w._hWnd
                ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                time.sleep(0.5)
            except Exception as e:
                print(f"[tg] win32 force fail: {e}", file=sys.stderr)
            return True
        except Exception as e:
            print(f"[tg] activate fail: {e}", file=sys.stderr)

    for p in TG_DESKTOP_PATHS:
        if Path(p).exists():
            subprocess.Popen([p])
            time.sleep(10)
            # Recursive call para maximize
            wins2 = gw.getWindowsWithTitle("Telegram")
            if wins2:
                try:
                    wins2[0].maximize()
                    wins2[0].activate()
                    time.sleep(1)
                except Exception:
                    pass
            return True
    return False


def _ocr_find(needle: str, retries: int = 3) -> tuple[int, int] | None:
    """Busca texto en pantalla con OCR. Retry algunos veces."""
    from jarvis_v2.skills.desktop_hybrid import find_text
    for _ in range(retries):
        coords = find_text(needle, case_sensitive=False)
        if coords:
            return coords
        time.sleep(2)
    return None


def _click_humano(x: int, y: int):
    from jarvis_v2.swarm.human_mouse import human_click
    human_click(x, y)


def _typewrite_humano(text: str):
    """Pyautogui write con interval variable, mas humano que .write directo."""
    import pyautogui, random
    pyautogui.write(text, interval=random.uniform(0.04, 0.09))


def _press(key: str):
    import pyautogui
    pyautogui.press(key)


def setup_telegram_bot(bot_name: str = "Jarvis V2",
                        bot_username_base: str = "jarvis_emmanuel_v2") -> dict:
    """Camina TG Desktop autonomamente y extrae el token."""
    if not _open_telegram_app():
        return {"ok": False, "error": "telegram_desktop_not_found",
                "paths_tried": TG_DESKTOP_PATHS}

    time.sleep(2)

    # 1. Click search (Ctrl+F suele abrir search en TG Desktop)
    import pyautogui
    pyautogui.hotkey("ctrl", "f")
    time.sleep(1.5)

    # 2. Tipear BotFather
    _typewrite_humano("BotFather")
    time.sleep(2)

    # 3. Click resultado: buscamos "BotFather" en la lista de results via OCR
    coords = _ocr_find("BotFather", retries=4)
    if not coords:
        return {"ok": False, "error": "botfather_not_found_via_ocr",
                "hint": "Asegurate de que Telegram Desktop este visible y maximizado"}
    _click_humano(*coords)
    time.sleep(2.5)

    # 4. Tipea /newbot en input
    _typewrite_humano("/newbot")
    _press("enter")
    time.sleep(3)

    # Wait for "what to call" response
    if not _ocr_find("what to call", retries=10):
        return {"ok": False, "error": "no_response_to_newbot",
                "hint": "Tal vez ya respondiste antes o BotFather no respondio"}

    # 5. Tipea nombre
    _typewrite_humano(bot_name)
    _press("enter")
    time.sleep(3)

    if not _ocr_find("username", retries=10):
        return {"ok": False, "error": "no_response_to_name"}

    # 6. Username con variantes
    token = None
    chosen_username = None
    for suffix in ("_bot", "_v2_bot", "_pro_bot", "_alpha_bot", "_local_bot"):
        uname = bot_username_base + suffix
        _typewrite_humano(uname)
        _press("enter")
        time.sleep(4)
        # Buscar texto que indique success o failure
        from jarvis_v2.skills.desktop_hybrid import scan_desktop
        scan = scan_desktop()
        all_text = " ".join(t["texto"] for t in scan["texto_detectado"])
        if "taken" in all_text.lower() or "already" in all_text.lower() or "invalid" in all_text.lower():
            continue
        # Buscar token pattern <digits>:<chars>
        m = re.search(r"(\d{9,10}):([A-Za-z0-9_-]{30,})", all_text)
        if m:
            token = f"{m.group(1)}:{m.group(2)}"
            chosen_username = uname
            break
    if not token:
        return {"ok": False, "error": "no_token_extracted",
                "hint": "Probable que OCR no leyo bien el token. Tomar screenshot manual."}

    # 7. Persistir
    env_path = ROOT / ".env"
    env_content = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    if "TELEGRAM_BOT_TOKEN=" in env_content:
        env_content = re.sub(r"TELEGRAM_BOT_TOKEN=.*",
                              f"TELEGRAM_BOT_TOKEN={token}", env_content)
    else:
        env_content += f"\nTELEGRAM_BOT_TOKEN={token}\n"
    env_path.write_text(env_content, encoding="utf-8")
    subprocess.run(["setx", "TELEGRAM_BOT_TOKEN", token],
                   capture_output=True, shell=True)

    return {
        "ok": True,
        "token_preview": token[:15] + "...",
        "bot_username": chosen_username,
        "saved_to": str(env_path),
        "next_step": "Setear TELEGRAM_ALLOWED_CHAT_ID y arrancar bridge",
    }


if __name__ == "__main__":
    r = setup_telegram_bot()
    print(json.dumps(r, ensure_ascii=False, indent=2))
