"""ui_tars_client.py - Cliente VM que pregunta al host UI-TARS service.

Reemplaza el patron 'Claude vision → coords' por 'UI-TARS → coords' cuando
disponible. Fallback a Claude vision si UI-TARS no responde.

Uso:
  from jarvis_swarm.ui_tars_client import predict_click_uitars
  coords = predict_click_uitars(screenshot_path, "click on Save button")
  if coords: pyautogui.click(coords[0], coords[1])
"""
from __future__ import annotations

import io
from pathlib import Path

UI_TARS_URL = "http://10.0.2.2:8090"


def is_uitars_available(timeout: float = 2.0) -> bool:
    try:
        import requests
        r = requests.get(f"{UI_TARS_URL}/health", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False


def predict_click_uitars(screenshot_path: str, task: str, timeout: float = 30.0) -> tuple[int, int] | None:
    """Pregunta al host UI-TARS: 'donde clickear para hacer X?'.

    Returns (x, y) en pixel coordinates o None si fallo.
    """
    try:
        import requests
    except ImportError:
        return None
    try:
        with open(screenshot_path, "rb") as f:
            files = {"file": (Path(screenshot_path).name, f, "image/png")}
            data = {"task": task}
            r = requests.post(f"{UI_TARS_URL}/predict_click",
                              files=files, data=data, timeout=timeout)
            if r.status_code == 200:
                payload = r.json()
                if payload.get("found"):
                    return (payload["x"], payload["y"])
    except Exception:
        pass
    return None
