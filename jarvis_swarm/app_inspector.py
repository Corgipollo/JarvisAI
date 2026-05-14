"""app_inspector.py — Para cada app, abre y mapea TODOS sus controles.

Cada 2h:
  1. Lee installed_apps de environment_map.json
  2. Selecciona app que NO ha sido inspeccionada en >7 dias
  3. Abre la app (via Win+R + nombre)
  4. Espera que cargue (2-5 seg)
  5. Captura UIA tree COMPLETO (todos los botones, menus, edit fields)
  6. Para cada control significativo, pregunta a Claude:
     "Que hace este boton/control en esta app?"
  7. Guarda en data/app_inventory/<app_name>.json:
        - lista de controles
        - posicion en pantalla
        - descripcion de funcion
        - shortcuts asociados
  8. Cierra la app
  9. Pasa a la siguiente

Otros agentes consultan app_inventory para responder al instante:
  "donde esta el boton Guardar en Word?" → Click en (X, Y) o Ctrl+S
  "como cambio el color de fondo en Photoshop?" → menu Image > Adjustments
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

DATA = ROOT / "data"
INVENTORY = DATA / "app_inventory"


class AppInspector(BaseAgent):
    name = "app_inspector"
    description = "Para cada app abre y mapea todos sus botones + funciones via Claude"
    tick_seconds = 7200  # 2 horas

    def __init__(self):
        super().__init__()
        INVENTORY.mkdir(parents=True, exist_ok=True)

    def get_apps_to_inspect(self) -> list[str]:
        """Lista de apps simples para inspeccionar (orden por urgencia)."""
        candidates = [
            "notepad", "calc", "mspaint", "explorer", "control",
            "snippingtool", "powershell", "cmd", "regedit", "taskmgr",
            "winver", "msinfo32", "dxdiag", "mstsc", "wordpad",
        ]
        # Filtra los que ya estan inspeccionados recientemente
        result = []
        cutoff = datetime.now() - timedelta(days=7)
        for app in candidates:
            inv_file = INVENTORY / f"{app}.json"
            if inv_file.exists():
                try:
                    d = json.loads(inv_file.read_text(encoding="utf-8"))
                    last_ts = datetime.fromisoformat(d.get("inspected_at", "1970-01-01"))
                    if last_ts > cutoff:
                        continue
                except Exception:
                    pass
            result.append(app)
        return result

    def open_app_via_run(self, app_name: str) -> bool:
        """Abre app via Win+R + nombre."""
        try:
            import pyautogui
            pyautogui.hotkey("win", "r")
            time.sleep(1.5)
            pyautogui.write(app_name, interval=0.05)
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(3)  # esperar carga
            return True
        except Exception as e:
            self.log(f"  abrir {app_name} fallo: {e}")
            return False

    def capture_full_uia(self, app_name: str) -> dict:
        """Captura UIA tree completo de la ventana activa."""
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    if w.is_active():
                        controls = []
                        for c in w.descendants()[:200]:
                            try:
                                text = c.window_text()
                                ctype = str(c.element_info.control_type)
                                rect = None
                                try:
                                    r = c.rectangle()
                                    rect = {"left": r.left, "top": r.top,
                                            "right": r.right, "bottom": r.bottom}
                                except Exception:
                                    pass
                                if text or ctype in ("Button", "MenuItem", "Tab",
                                                      "ComboBox", "Edit"):
                                    controls.append({
                                        "text": text[:100],
                                        "type": ctype,
                                        "rect": rect,
                                    })
                            except Exception:
                                continue
                        return {
                            "window_title": w.window_text(),
                            "controls": controls,
                        }
                except Exception:
                    continue
        except ImportError:
            return {"error": "pywinauto no instalado"}
        except Exception as e:
            return {"error": str(e)}
        return {}

    def ask_claude_describe_controls(self, app_name: str, controls: list[dict]) -> dict:
        """Pide a Claude que describa cada control significativo."""
        try:
            from jarvis_bridge.jarvis_brain import ask_claude_json
        except ImportError:
            return {}
        # Limitar a 30 controles para no saturar
        top_controls = [c for c in controls if c.get("text") or
                        c.get("type") in ("Button", "MenuItem", "ComboBox")][:30]
        prompt = (
            f"Eres app inspector de Jarvis. App actual: {app_name}\n"
            f"Lista de controles UIA detectados:\n"
            + "\n".join(f"- [{c['type']}] {c.get('text','')}" for c in top_controls)
            + f"\n\nPara cada control, describe en 1 frase QUE HACE en la app. "
            f"Responde JSON: "
            f'{{"control_descriptions": [{{"text": "...", "what_it_does": "..."}}]}}'
        )
        return ask_claude_json(prompt, schema_hint='{"control_descriptions": [...]}') or {}

    def close_active_window(self):
        """Cierra ventana activa con Alt+F4."""
        try:
            import pyautogui
            pyautogui.hotkey("alt", "f4")
            time.sleep(1)
        except Exception:
            pass

    def step(self):
        candidates = self.get_apps_to_inspect()
        if not candidates:
            return {"ok": True, "action": "all_inspected_recently"}
        app = candidates[0]
        self.log(f"=== inspecting {app} ===")

        if not self.open_app_via_run(app):
            return {"ok": False, "error": f"open {app} failed"}

        uia = self.capture_full_uia(app)
        if not uia.get("controls"):
            self.close_active_window()
            return {"ok": False, "error": "no UIA controls"}

        descriptions = self.ask_claude_describe_controls(app, uia["controls"])

        inventory = {
            "app": app,
            "inspected_at": datetime.now().isoformat(),
            "window_title": uia.get("window_title"),
            "controls": uia.get("controls", []),
            "control_descriptions": descriptions.get("control_descriptions", []),
        }
        inv_file = INVENTORY / f"{app}.json"
        inv_file.write_text(json.dumps(inventory, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        self.log(f"  inventario guardado: {len(uia['controls'])} controles, "
                 f"{len(descriptions.get('control_descriptions', []))} descritos")

        self.close_active_window()
        return {"ok": True, "action": "app_inspected", "app": app,
                "controls": len(uia["controls"])}


if __name__ == "__main__":
    AppInspector().run_loop()
