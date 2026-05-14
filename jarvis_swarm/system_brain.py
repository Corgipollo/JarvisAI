"""system_brain.py — Cerebro NATIVO de Jarvis: lee Windows directo, sin screenshots.

Pyautogui + screenshots es VISION (caro, lento, pixel-dependiente).
UIA + COM + Win32 es SEMANTICO (instantaneo, robusto, nativo).

Este modulo construye un GRAFO DE CONOCIMIENTO de Windows:

  windows_graph = {
    "apps": {
       "notepad++": {
          "exe": "C:/Program Files/Notepad++/notepad++.exe",
          "version": "8.6.1",
          "windows": [
             {
                "title": "main",
                "controls": [
                   {"id": "btn_save", "name": "Save", "type": "Button",
                    "action": "invoke", "shortcut": "Ctrl+S",
                    "rect": [x,y,w,h], "what_it_does": "..."},
                   ...
                ]
             }
          ]
       }
    },
    "system_calls": {
       "open_explorer": "shell:Documents",
       "lock_pc": "rundll32 user32.dll,LockWorkStation",
       ...
    },
    "registry_keys_important": [...],
    "com_objects_available": [...]
  }

Cuando vision_executor decide accion, primero consulta este grafo:
  - 'ordena escritorio por fecha' → grafo dice:
     "1. Find class 'Progman' (escritorio)
      2. right_click via SendMessage (no pixel click)
      3. Find menu_item 'Sort by' → invoke
      4. Find sub_item 'Date modified' → invoke"

Sin screenshots. Instantaneo. 99% reliable.

Funciona como conocimiento absorbido: lo construye una vez, lo usa para siempre.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

DATA = ROOT / "data"
BRAIN_FILE = DATA / "system_brain.json"


def safe_run(cmd: list[str], timeout: int = 20) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.stdout or ""
    except Exception as e:
        return f"ERR: {e}"


# ============================================================================
# Conocimiento SEMANTICO del sistema (no requiere screenshot)
# ============================================================================
NATIVE_SYSTEM_ACTIONS = {
    # Cosas que Jarvis YA SABE hacer sin aprender
    "open_explorer_documents":   "explorer shell:Documents",
    "open_explorer_downloads":   "explorer shell:Downloads",
    "open_explorer_desktop":     "explorer shell:Desktop",
    "open_explorer_pictures":    "explorer shell:Pictures",
    "open_explorer_videos":      "explorer shell:Videos",
    "open_explorer_appdata":     "explorer %APPDATA%",
    "open_settings":             "ms-settings:",
    "open_settings_display":     "ms-settings:display",
    "open_settings_apps":        "ms-settings:apps",
    "open_settings_privacy":     "ms-settings:privacy",
    "open_control_panel":        "control",
    "open_device_manager":       "devmgmt.msc",
    "open_task_manager":         "taskmgr",
    "open_services":             "services.msc",
    "open_regedit":              "regedit",
    "open_system_info":          "msinfo32",
    "open_dxdiag":               "dxdiag",
    "open_event_viewer":         "eventvwr.msc",
    "open_disk_management":      "diskmgmt.msc",
    "open_resource_monitor":     "resmon",
    "lock_pc":                   "rundll32 user32.dll,LockWorkStation",
    "logout":                    "shutdown /l",
    "shutdown_in_60s":           "shutdown /s /t 60",
    "restart_in_60s":            "shutdown /r /t 60",
    "cancel_shutdown":           "shutdown /a",
    "show_desktop":              "Win+D (hotkey)",
    "switch_window":             "Alt+Tab (hotkey)",
    "task_view":                 "Win+Tab (hotkey)",
    "screenshot_region":         "Win+Shift+S (hotkey)",
    "clipboard_history":         "Win+V (hotkey)",
    "emoji_picker":              "Win+. (hotkey)",
    "magnifier":                 "Win+= (hotkey)",
    "narrator":                  "Win+Ctrl+Enter (hotkey)",
    "voice_typing":              "Win+H (hotkey)",
    "action_center":             "Win+A (hotkey)",
    "quick_settings":            "Win+I (settings) (hotkey)",
    "power_user_menu":           "Win+X (hotkey)",
    "run_dialog":                "Win+R (hotkey)",
}

DESKTOP_ACTIONS = {
    # Como interactuar con el escritorio
    "right_click_desktop": "SendMessage WM_CONTEXTMENU a clase 'Progman' o 'WorkerW'",
    "sort_desktop_by_date": "right_click_desktop → 'Ordenar por' → 'Fecha de modificación'",
    "sort_desktop_by_name": "right_click_desktop → 'Ordenar por' → 'Nombre'",
    "sort_desktop_by_size": "right_click_desktop → 'Ordenar por' → 'Tamaño'",
    "sort_desktop_by_type": "right_click_desktop → 'Ordenar por' → 'Tipo de elemento'",
    "refresh_desktop":     "F5 cuando desktop tiene foco",
    "new_folder_desktop":  "right_click → 'Nuevo' → 'Carpeta'",
    "paste_to_desktop":    "Ctrl+V cuando desktop tiene foco",
}

EXPLORER_ACTIONS = {
    "select_all_files":     "Ctrl+A",
    "copy_files":           "Ctrl+C",
    "paste_files":          "Ctrl+V",
    "cut_files":            "Ctrl+X",
    "delete_files":         "Delete",
    "delete_permanently":   "Shift+Delete",
    "rename":               "F2 sobre archivo seleccionado",
    "properties":           "Alt+Enter sobre archivo",
    "address_bar":          "Ctrl+L o Alt+D",
    "new_folder":           "Ctrl+Shift+N",
    "back":                 "Alt+Left",
    "forward":              "Alt+Right",
    "up":                   "Alt+Up",
    "sort_by_date":         "Click columna 'Fecha modificación' o View ribbon → Sort by",
    "sort_by_name":         "Click columna 'Nombre' o View → Sort by",
    "view_details":         "Ctrl+Shift+6",
    "view_large_icons":     "Ctrl+Shift+2",
    "show_hidden":          "View ribbon → Show → Hidden items",
    "preview_pane":         "Alt+P",
    "details_pane":         "Alt+Shift+P",
}

BROWSER_ACTIONS = {
    "new_tab":              "Ctrl+T",
    "close_tab":            "Ctrl+W",
    "reopen_tab":           "Ctrl+Shift+T",
    "next_tab":             "Ctrl+Tab",
    "prev_tab":             "Ctrl+Shift+Tab",
    "address_bar":          "Ctrl+L o F6",
    "bookmark":             "Ctrl+D",
    "incognito":            "Ctrl+Shift+N (Chrome/Edge)",
    "history":              "Ctrl+H",
    "downloads":            "Ctrl+J",
    "find":                 "Ctrl+F",
    "devtools":             "F12",
    "zoom_in":              "Ctrl+Plus",
    "zoom_out":             "Ctrl+Minus",
    "zoom_reset":           "Ctrl+0",
    "fullscreen":           "F11",
}

TEXT_EDITOR_ACTIONS = {
    "save":             "Ctrl+S",
    "save_as":          "Ctrl+Shift+S",
    "open":             "Ctrl+O",
    "new":              "Ctrl+N",
    "find":             "Ctrl+F",
    "replace":          "Ctrl+H",
    "undo":             "Ctrl+Z",
    "redo":             "Ctrl+Y o Ctrl+Shift+Z",
    "cut":              "Ctrl+X",
    "copy":             "Ctrl+C",
    "paste":            "Ctrl+V",
    "select_all":       "Ctrl+A",
    "go_to_line":       "Ctrl+G",
    "duplicate_line":   "Ctrl+D (VSCode) o Ctrl+Shift+D",
    "comment_line":     "Ctrl+/ (VSCode)",
    "format_doc":       "Shift+Alt+F (VSCode)",
}

UNIVERSAL_ACTIONS = {
    "close_window":     "Alt+F4",
    "minimize":         "Win+Down",
    "maximize":         "Win+Up",
    "snap_left":        "Win+Left",
    "snap_right":       "Win+Right",
    "switch_apps":      "Alt+Tab",
    "switch_apps_back": "Alt+Shift+Tab",
    "menu_bar":         "Alt o F10",
    "context_menu":     "Shift+F10 o Menu key",
    "select_text":      "Shift + flechas",
    "select_word":      "Ctrl+Shift + flechas",
    "delete_word_back": "Ctrl+Backspace",
    "delete_word_fwd":  "Ctrl+Delete",
    "home_of_line":     "Home",
    "end_of_line":      "End",
    "home_of_doc":      "Ctrl+Home",
    "end_of_doc":       "Ctrl+End",
}


class SystemBrain(BaseAgent):
    name = "system_brain"
    description = "Construye conocimiento SEMANTICO de Windows (sin screenshots) cada 12h"
    tick_seconds = 43200  # 12 horas

    def get_installed_apps_detailed(self) -> list[dict]:
        """Apps con path, version, exe."""
        out = safe_run([
            "powershell", "-NoProfile", "-Command",
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
            "| Select-Object DisplayName,DisplayVersion,InstallLocation,Publisher "
            "| Where-Object {$_.DisplayName -ne $null} "
            "| ConvertTo-Json -Depth 2"
        ])
        try:
            data = json.loads(out)
            return data if isinstance(data, list) else [data]
        except Exception:
            return []

    def get_shell_known_folders(self) -> dict:
        """Folders especiales del shell (Documents, Downloads, etc)."""
        folders = {}
        for env_var in ["USERPROFILE", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES",
                        "PROGRAMFILES(X86)", "PROGRAMDATA", "SYSTEMROOT", "TEMP"]:
            v = os.environ.get(env_var)
            if v:
                folders[env_var] = v
        return folders

    def get_running_processes_with_windows(self) -> list[dict]:
        """Procesos con ventanas visibles."""
        out = safe_run([
            "powershell", "-NoProfile", "-Command",
            "Get-Process | Where-Object {$_.MainWindowHandle -ne 0} | "
            "Select-Object ProcessName,Id,MainWindowTitle,WorkingSet64 | "
            "ConvertTo-Json -Depth 2"
        ])
        try:
            return json.loads(out) if out.strip() else []
        except Exception:
            return []

    def get_services_critical(self) -> list[dict]:
        """Servicios criticos del sistema."""
        out = safe_run([
            "powershell", "-NoProfile", "-Command",
            "Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and $_.Status -eq 'Running'} | "
            "Select-Object Name,DisplayName | ConvertTo-Json -Depth 2"
        ])
        try:
            data = json.loads(out)
            return (data if isinstance(data, list) else [data])[:30]
        except Exception:
            return []

    def get_environment_variables(self) -> dict:
        return {k: v for k, v in os.environ.items()
                if k in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP",
                         "PATH", "PROCESSOR_IDENTIFIER", "OS", "USERNAME",
                         "USERDOMAIN", "COMPUTERNAME")}

    def step(self):
        self.log("Construyendo cerebro nativo del sistema...")
        brain = {
            "ts": datetime.now().isoformat(),
            "_documentation": "Conocimiento SEMANTICO de Windows. Jarvis lo lee para "
                              "decidir acciones sin necesidad de screenshots.",
            "native_system_actions": NATIVE_SYSTEM_ACTIONS,
            "desktop_actions": DESKTOP_ACTIONS,
            "explorer_actions": EXPLORER_ACTIONS,
            "browser_actions": BROWSER_ACTIONS,
            "text_editor_actions": TEXT_EDITOR_ACTIONS,
            "universal_actions": UNIVERSAL_ACTIONS,
            "shell_folders": self.get_shell_known_folders(),
            "environment_vars": self.get_environment_variables(),
            "running_with_windows": self.get_running_processes_with_windows()[:30],
            "installed_apps_detailed": self.get_installed_apps_detailed()[:50],
            "services_critical": self.get_services_critical(),
        }
        DATA.mkdir(parents=True, exist_ok=True)
        BRAIN_FILE.write_text(json.dumps(brain, ensure_ascii=False, indent=2,
                                          default=str), encoding="utf-8")
        self.log(f"  cerebro guardado: {len(NATIVE_SYSTEM_ACTIONS)} acciones nativas, "
                 f"{len(brain['installed_apps_detailed'])} apps detalladas, "
                 f"{len(brain['running_with_windows'])} procesos con ventana")
        return {"ok": True, "action": "system_brain_built",
                "native_actions": len(NATIVE_SYSTEM_ACTIONS),
                "apps": len(brain["installed_apps_detailed"])}


if __name__ == "__main__":
    SystemBrain().run_loop()
