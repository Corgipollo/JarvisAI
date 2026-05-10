"""mouse.py — Skills de mouse fino para Jarvis.

Wrapper limpio sobre pyautogui con timing humano (jitter en delays).
Todas las funciones son sincronas, devuelven dict con success/details.
"""
from __future__ import annotations

import random
import time
from typing import Optional

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # mover mouse a esquina superior izq aborta
    pyautogui.PAUSE = 0.05
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False


def _human_delay(base: float = 0.1, jitter: float = 0.08) -> None:
    """Delay humano: base + random(0, jitter)."""
    time.sleep(base + random.random() * jitter)


def click(x: int, y: int, button: str = "left", clicks: int = 1) -> dict:
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    try:
        pyautogui.moveTo(x, y, duration=0.2 + random.random() * 0.2)
        _human_delay()
        pyautogui.click(x=x, y=y, clicks=clicks, button=button, interval=0.08)
        return {"success": True, "x": x, "y": y, "button": button, "clicks": clicks}
    except Exception as e:
        return {"success": False, "error": str(e)}


def double_click(x: int, y: int) -> dict:
    return click(x, y, clicks=2)


def right_click(x: int, y: int) -> dict:
    return click(x, y, button="right")


def drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.6) -> dict:
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    try:
        pyautogui.moveTo(x1, y1, duration=0.2)
        _human_delay()
        pyautogui.dragTo(x2, y2, duration=duration, button="left")
        return {"success": True, "from": (x1, y1), "to": (x2, y2)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def hover(x: int, y: int, duration: float = 0.3) -> dict:
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    pyautogui.moveTo(x, y, duration=duration)
    return {"success": True, "x": x, "y": y}


def scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None) -> dict:
    """amount > 0 scroll up, < 0 scroll down."""
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    if x is not None and y is not None:
        pyautogui.moveTo(x, y, duration=0.2)
    pyautogui.scroll(amount)
    return {"success": True, "amount": amount}


def get_position() -> dict:
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    pos = pyautogui.position()
    return {"success": True, "x": pos.x, "y": pos.y}


def screen_size() -> dict:
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    s = pyautogui.size()
    return {"success": True, "width": s.width, "height": s.height}


def type_text(text: str, interval: float = 0.04) -> dict:
    """Escribir texto con timing humano (jitter en interval)."""
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    try:
        # Jitter humano: cada letra entre 0.03 y 0.08s
        for char in text:
            pyautogui.typewrite(char, interval=0)
            time.sleep(interval + random.random() * 0.04)
        return {"success": True, "chars": len(text)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def press_keys(*keys: str) -> dict:
    """press_keys('ctrl', 'c') o press_keys('enter')."""
    if not HAS_PYAUTOGUI:
        return {"success": False, "error": "pyautogui no instalado"}
    try:
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return {"success": True, "keys": list(keys)}
    except Exception as e:
        return {"success": False, "error": str(e)}
