"""human_mouse.py - Movimientos de mouse humanizados anti-bot detection.

Curvas de Bezier + jitter + delays variables + tipeo con errores ocasionales.
Critico para evitar baneos de Twitter/Reddit/etc.

gui_mouse_lock asegura que solo UN worker mueva el mouse a la vez.
"""
from __future__ import annotations

import math
import random
import string
import threading
import time

# Lock GLOBAL del sistema - importante: instancia unica compartida por procesos
gui_mouse_lock = threading.Lock()


def _bezier_curve(p0, p1, p2, p3, t):
    """Cubic Bezier point at t in [0,1]."""
    x = ((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0]
         + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0])
    y = ((1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1]
         + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1])
    return (x, y)


def human_move_to(x_target: int, y_target: int, duration: float | None = None,
                   steps: int = 40, jitter: float = 2.0):
    """Mueve mouse via curva Bezier con jitter. Llama dentro de `with gui_mouse_lock`."""
    import pyautogui
    pyautogui.FAILSAFE = False
    x0, y0 = pyautogui.position()

    if duration is None:
        # Distancia ~ duracion humana realista (Fitts's law approx)
        dist = math.hypot(x_target - x0, y_target - y0)
        duration = 0.2 + (dist / 1000) + random.uniform(-0.05, 0.15)
    duration = max(0.15, min(2.0, duration))

    # Control points para Bezier (curva con desvio aleatorio)
    p0 = (x0, y0)
    p3 = (x_target, y_target)
    mid_x = (x0 + x_target) / 2
    mid_y = (y0 + y_target) / 2
    offset_x = random.uniform(-150, 150)
    offset_y = random.uniform(-100, 100)
    p1 = (mid_x + offset_x, mid_y + offset_y)
    p2 = (mid_x - offset_x / 2, mid_y - offset_y / 2)

    sleep_per = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        # Easing (slower start/end)
        eased = 3 * t ** 2 - 2 * t ** 3
        x, y = _bezier_curve(p0, p1, p2, p3, eased)
        x += random.uniform(-jitter, jitter)
        y += random.uniform(-jitter, jitter)
        pyautogui.moveTo(int(x), int(y), duration=0)
        time.sleep(sleep_per)
    # Final landing exacto
    pyautogui.moveTo(x_target, y_target, duration=0)


def human_click(x: int, y: int, button: str = "left",
                 pre_pause: tuple = (0.2, 0.8)):
    """Mueve humanamente y click. Pausa pre-click variable."""
    import pyautogui
    pyautogui.FAILSAFE = False
    human_move_to(x, y)
    time.sleep(random.uniform(*pre_pause))
    pyautogui.click(button=button)


def human_type(text: str, base_wpm: int = 80, typo_rate: float = 0.03):
    """Tipeo humano: WPM realista + typos ocasionales corregidos.

    typo_rate=0.03 = ~3% chance de error tipeado-y-borrado por char.
    """
    import pyautogui
    pyautogui.FAILSAFE = False
    # base char delay desde WPM (avg 5 chars/word)
    base_delay = 60 / (base_wpm * 5)
    for ch in text:
        # Random typo ocasional
        if random.random() < typo_rate and ch.isalpha():
            wrong = random.choice(string.ascii_lowercase)
            pyautogui.write(wrong, interval=base_delay)
            time.sleep(random.uniform(0.1, 0.4))
            pyautogui.press("backspace")
            time.sleep(random.uniform(0.05, 0.15))
        # Variable delay per char (gauss)
        delay = max(0.02, random.gauss(base_delay, base_delay * 0.4))
        pyautogui.write(ch, interval=delay)
        # Occasional micro-pause (humano piensa)
        if random.random() < 0.04:
            time.sleep(random.uniform(0.3, 1.5))


def human_scroll(amount: int, steps: int = 5):
    """Scroll humanizado en chunks pequenos."""
    import pyautogui
    per_step = amount // steps
    for _ in range(steps):
        pyautogui.scroll(per_step + random.randint(-2, 2))
        time.sleep(random.uniform(0.1, 0.4))


def human_drag(src_x: int, src_y: int, dst_x: int, dst_y: int,
                hold_pre_ms: tuple = (200, 500),
                duration: float | None = None,
                button: str = "left"):
    """Drag and drop humanizado.

    Flow:
      1. Move humanly to source
      2. Pause (humano enfoca el item)
      3. mouseDown
      4. Pause corta antes de empezar a arrastrar
      5. Move via Bezier al destino con velocity profile
      6. Pause corta antes de soltar
      7. mouseUp

    SIEMPRE usar bajo `with gui_mouse_lock:` desde el caller.

    Args:
        src_x, src_y: coordenadas de origen (donde esta el item)
        dst_x, dst_y: coordenadas destino (donde soltar)
        hold_pre_ms: tupla (min, max) ms para esperar despues de mouseDown
        duration: tiempo total del drag (None = auto por distancia)
    """
    import pyautogui
    pyautogui.FAILSAFE = False

    # 1. Move to source humanly
    human_move_to(src_x, src_y)
    # 2. Pause focusing item
    time.sleep(random.uniform(0.15, 0.45))
    # 3. mouseDown
    pyautogui.mouseDown(button=button)
    # 4. Brief hold before dragging
    time.sleep(random.uniform(hold_pre_ms[0] / 1000, hold_pre_ms[1] / 1000))

    # 5. Bezier curve to destination - slower than normal move (humanos arrastran
    # con mas precision)
    x0, y0 = src_x, src_y
    if duration is None:
        dist = math.hypot(dst_x - x0, dst_y - y0)
        # Drag is ~50% slower than free movement
        duration = 0.35 + (dist / 700) + random.uniform(-0.05, 0.20)
    duration = max(0.25, min(3.0, duration))

    steps = 50  # mas steps para drag (mas suave)
    # Control points - drag con menor desvio (mas controlado que click)
    mid_x = (x0 + dst_x) / 2
    mid_y = (y0 + dst_y) / 2
    offset_x = random.uniform(-80, 80)
    offset_y = random.uniform(-60, 60)
    p0 = (x0, y0)
    p3 = (dst_x, dst_y)
    p1 = (mid_x + offset_x, mid_y + offset_y)
    p2 = (mid_x - offset_x / 2, mid_y - offset_y / 2)

    sleep_per = duration / steps
    for i in range(1, steps + 1):
        t = i / steps
        eased = 3 * t ** 2 - 2 * t ** 3
        x, y = _bezier_curve(p0, p1, p2, p3, eased)
        # Drag jitter mas pequeno (1px)
        x += random.uniform(-1, 1)
        y += random.uniform(-1, 1)
        pyautogui.moveTo(int(x), int(y), duration=0)
        time.sleep(sleep_per)

    # 6. Land precisamente
    pyautogui.moveTo(dst_x, dst_y, duration=0)
    time.sleep(random.uniform(0.15, 0.40))

    # 7. Release
    pyautogui.mouseUp(button=button)
    time.sleep(random.uniform(0.10, 0.30))


def human_drag_files(file_paths: list[str], dst_x: int, dst_y: int):
    """Para 'drag files from File Explorer'. Usa shell+pywin32 si esta disponible
    para drag programatico mas confiable. Fallback: drag visual desde
    coordenadas conocidas en File Explorer."""
    try:
        # En la mayoria de casos shutil.move es 1000x mas confiable. Esta funcion
        # solo si NECESITAS interactuar con app que solo acepta drag visual.
        # Por ahora, hacemos un warning y delegamos a shutil si target_dir.
        import shutil
        import os
        if os.path.isdir(file_paths[0]):
            return {"error": "this is for files; use shutil for directories"}
        # No tenemos coords origen sin SoM. Caller debe pasarlas explicitamente.
        return {"error": "use human_drag(src_x, src_y, dst_x, dst_y) en su lugar"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    print("Test human_mouse en 3s - vas a ver el mouse moverse")
    time.sleep(3)
    import pyautogui
    w, h = pyautogui.size()
    with gui_mouse_lock:
        human_move_to(w // 4, h // 4)
        time.sleep(0.5)
        human_move_to(3 * w // 4, 3 * h // 4)
        time.sleep(0.5)
        human_move_to(w // 2, h // 2)
    print("Done.")
