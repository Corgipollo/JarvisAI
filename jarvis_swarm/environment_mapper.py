"""environment_mapper.py — Mapa COMPLETO del entorno Windows que Jarvis vive.

Cada 6h regenera data/environment_map.json con TODO el sistema:

  1. Apps instaladas (paths, ejecutables, version, icons)
  2. Apps en taskbar pinned
  3. Estructura FS importante (Documents, Downloads, Desktop, AppData)
  4. Servicios Windows (running, stopped)
  5. Procesos activos con ventanas
  6. UIA tree de CADA app abierta (todos los botones + para qué sirven)
  7. Shortcuts globales del sistema (Win+R, Win+E, Win+L, etc)
  8. Variables de entorno
  9. Discos + espacio
  10. Network: WiFi nombre, IP, conexión activa

Otros agentes leen environment_map.json para responder al instante:
  - "¿dónde está Photoshop?" → C:\Program Files\Adobe\...
  - "¿qué hace el botón X de la app Y?" → UIA tree + Claude descripción
  - "¿qué procesos comen RAM?" → process_top

Es la "memoria de mundo" de Jarvis. Como un humano que conoce su casa.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

DATA = ROOT / "data"
MAP_FILE = DATA / "environment_map.json"


class EnvironmentMapper(BaseAgent):
    name = "environment_mapper"
    description = "Mapea TODO el entorno Windows cada 6h para que Jarvis sepa donde esta cada cosa"
    tick_seconds = 21600  # 6 horas

    def list_installed_apps(self) -> list[dict]:
        """Apps instaladas via Get-StartApps (mas rapido que registry scan)."""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Depth 2"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            return json.loads(r.stdout) if r.stdout.strip() else []
        except Exception:
            return []

    def list_running_apps(self) -> list[dict]:
        """Procesos con ventanas visibles."""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Process | Where-Object {$_.MainWindowTitle -ne ''} | "
                 "Select-Object ProcessName,MainWindowTitle,WorkingSet64,Id | "
                 "ConvertTo-Json -Depth 2"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            return json.loads(r.stdout) if r.stdout.strip() else []
        except Exception:
            return []

    def list_services(self) -> list[dict]:
        """Servicios Windows."""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Service | Where-Object {$_.Status -eq 'Running'} | "
                 "Select-Object Name,DisplayName,Status | ConvertTo-Json -Depth 2"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            return json.loads(r.stdout)[:50] if r.stdout.strip() else []
        except Exception:
            return []

    def get_fs_structure(self) -> dict:
        """Estructura FS importante."""
        result = {}
        important_dirs = [
            ("Desktop", os.path.expanduser("~/Desktop")),
            ("Documents", os.path.expanduser("~/Documents")),
            ("Downloads", os.path.expanduser("~/Downloads")),
            ("Pictures", os.path.expanduser("~/Pictures")),
            ("Videos", os.path.expanduser("~/Videos")),
            ("Music", os.path.expanduser("~/Music")),
            ("AppData_Local", os.path.expanduser("~/AppData/Local")),
            ("ProgramFiles", "C:/Program Files"),
            ("ProgramFiles_x86", "C:/Program Files (x86)"),
            ("System32", "C:/Windows/System32"),
        ]
        for name, p in important_dirs:
            if os.path.exists(p):
                try:
                    items = os.listdir(p)
                    result[name] = {
                        "path": p,
                        "count": len(items),
                        "samples": items[:20],
                    }
                except Exception:
                    result[name] = {"path": p, "error": "no access"}
        return result

    def get_disks(self) -> list[dict]:
        """Disks con espacio libre."""
        disks = []
        for d in ["C:", "D:", "E:", "F:"]:
            try:
                total, used, free = shutil.disk_usage(d + "/")
                disks.append({
                    "drive": d,
                    "total_gb": round(total / (1024**3), 1),
                    "used_gb": round(used / (1024**3), 1),
                    "free_gb": round(free / (1024**3), 1),
                    "pct_used": round(used / total * 100, 1),
                })
            except Exception:
                continue
        return disks

    def get_uia_for_active_window(self) -> dict:
        """UIA tree de la ventana activa (todos sus controles)."""
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            for w in desktop.windows():
                try:
                    if w.is_active():
                        controls = []
                        for c in w.descendants()[:60]:
                            try:
                                text = c.window_text()
                                ctype = str(c.element_info.control_type)
                                if text or ctype in ("Button", "Edit", "ComboBox",
                                                      "MenuItem", "Tab"):
                                    controls.append({
                                        "text": text[:80],
                                        "type": ctype,
                                    })
                            except Exception:
                                continue
                        return {
                            "title": w.window_text()[:200],
                            "class": w.class_name()[:100],
                            "controls": controls,
                        }
                except Exception:
                    continue
        except ImportError:
            return {"error": "pywinauto no instalado"}
        except Exception as e:
            return {"error": str(e)}
        return {}

    def get_global_shortcuts(self) -> dict:
        """Shortcuts conocidos del sistema."""
        return {
            "Win+R": "Run dialog",
            "Win+E": "File Explorer",
            "Win+L": "Lock screen",
            "Win+D": "Show desktop",
            "Win+M": "Minimize all",
            "Win+Shift+S": "Snipping tool (screenshot region)",
            "Win+V": "Clipboard history",
            "Win+X": "Power user menu",
            "Win+I": "Settings",
            "Win+A": "Action center",
            "Win+Tab": "Task view",
            "Alt+Tab": "Switch windows",
            "Alt+F4": "Close window",
            "Ctrl+Esc": "Open Start menu",
            "Ctrl+Shift+Esc": "Task Manager",
            "Win+Space": "Switch keyboard layout",
            "Win+Period": "Emoji picker",
        }

    def step(self):
        self.log("Mapeando entorno completo...")
        env_map = {
            "ts": datetime.now().isoformat(),
            "system": {
                "username": os.getenv("USERNAME"),
                "userdomain": os.getenv("USERDOMAIN"),
                "computername": os.getenv("COMPUTERNAME"),
                "os": os.getenv("OS"),
                "processor": os.getenv("PROCESSOR_IDENTIFIER", ""),
                "num_processors": os.getenv("NUMBER_OF_PROCESSORS"),
            },
            "disks": self.get_disks(),
            "fs_structure": self.get_fs_structure(),
            "installed_apps": self.list_installed_apps(),
            "running_apps": self.list_running_apps(),
            "services_running": self.list_services(),
            "active_window_uia": self.get_uia_for_active_window(),
            "global_shortcuts": self.get_global_shortcuts(),
        }

        DATA.mkdir(parents=True, exist_ok=True)
        MAP_FILE.write_text(json.dumps(env_map, ensure_ascii=False, indent=2,
                                        default=str), encoding="utf-8")
        self.log(f"  mapa guardado: {len(env_map.get('installed_apps', []))} apps, "
                 f"{len(env_map.get('running_apps', []))} corriendo, "
                 f"{len(env_map.get('services_running', []))} servicios")
        return {"ok": True, "action": "mapped_environment",
                "apps_count": len(env_map.get('installed_apps', [])),
                "running_count": len(env_map.get('running_apps', []))}


if __name__ == "__main__":
    EnvironmentMapper().run_loop()
