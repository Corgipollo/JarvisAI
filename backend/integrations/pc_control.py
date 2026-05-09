"""
Control de PC para Jarvis — abrir apps, archivos, comandos del sistema.

================================================================================
FILOSOFIA OPERATIVA — "NO ME DETENGO HASTA TENERLO"
================================================================================

Cuando Emmanuel le pide a Jarvis "abre X", Jarvis NO debe rendirse al primer
intento. Debe iterar con varias estrategias hasta lograrlo, y SOLO declarar
fracaso despues de probar TODAS.

Cascada estandar para abrir cualquier app (en orden):

  1. **Start Menu Search** (lo que hace un humano) — tecla Windows + escribir
     nombre + Enter. Funciona para CASI todo lo instalado en Windows porque
     Windows Search indexa apps Microsoft Store, classic, portable pinned.
     NUNCA usar Win+R / cuadro Ejecutar — falla con apps que no estan en PATH.

  2. **URI / protocolo** — `os.startfile("telegram:")`, `start spotify:`,
     `start discord:`. Las apps modernas registran un protocolo. Si esta
     instalada via Microsoft Store, usualmente el protocolo es el camino
     mas robusto.

  3. **Path absoluto conocido** — diccionario `KNOWN_PATHS` con rutas
     tipicas de instalacion en Windows (`%LOCALAPPDATA%\\Programs\\...`,
     `C:\\Program Files\\...`, etc.).

  4. **Registry App Paths** — Windows tiene la clave
     `HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths`
     que mapea nombres ejecutables a rutas. Es lo que usa el comando
     `start` internamente.

  5. **Walk recursivo** ultimo recurso — buscar el .exe en
     `%LOCALAPPDATA%\\Programs`, `%APPDATA%`, `C:\\Program Files`,
     `C:\\Program Files (x86)`, `WindowsApps`.

Despues de cada intento, VERIFICAR si la app esta realmente corriendo
(pygetwindow + psutil). Si no, pasar a la siguiente estrategia.

================================================================================
PATRON HUMANO PARA ABRIR APPS — IMPRESCINDIBLE
================================================================================

  pyautogui.press('win')                       # tecla Windows sola
  time.sleep(0.6)                              # esperar Start Menu
  pyautogui.typewrite("telegram", interval=0.04)
  time.sleep(0.4)                              # esperar filtrado
  pyautogui.press('enter')                     # lanza top result

Validado 2026-05-09 con Telegram. Es el patron #1 universal en Windows 10/11.

================================================================================
KNOWLEDGE BASE — PATHS TIPICOS DE APPS EN WINDOWS
================================================================================

| App | Path tipico | Protocolo URI |
|-----|-------------|---------------|
| Telegram Desktop | %LOCALAPPDATA%\\Programs\\Telegram Desktop\\Telegram.exe | telegram: |
| Discord | %LOCALAPPDATA%\\Discord\\Update.exe --processStart Discord.exe | discord: |
| Spotify | %APPDATA%\\Spotify\\Spotify.exe | spotify: |
| Chrome | C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe | chrome (en PATH) |
| Firefox | C:\\Program Files\\Mozilla Firefox\\firefox.exe | firefox (en PATH) |
| VS Code | %LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe | vscode:// |
| Obsidian | %LOCALAPPDATA%\\Obsidian\\Obsidian.exe | obsidian:// |
| Steam | C:\\Program Files (x86)\\Steam\\steam.exe | steam:// |
| Slack | %LOCALAPPDATA%\\slack\\slack.exe | slack:// |
| Notion | %LOCALAPPDATA%\\Programs\\Notion\\Notion.exe | notion:// |
| Postman | %LOCALAPPDATA%\\Postman\\Postman.exe | - |
| Zoom | %APPDATA%\\Zoom\\bin\\Zoom.exe | zoommtg:// |
| Teams | %LOCALAPPDATA%\\Programs\\Teams\\current\\Teams.exe | msteams:// |
| Brave | %LOCALAPPDATA%\\BraveSoftware\\Brave-Browser\\Application\\brave.exe | brave:// |
| Opera GX | %LOCALAPPDATA%\\Programs\\Opera GX\\opera.exe | opera:// |
| Edge | C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe | microsoft-edge: |
"""
from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

# Dependencias opcionales — degradan elegantemente si no estan
try:
    import pyautogui
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


# ============================================================================
# KNOWLEDGE BASE — Apps + protocolos + paths absolutos + nombres de proceso
# ============================================================================

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
APPDATA = os.environ.get("APPDATA", "")
PROGRAMFILES = os.environ.get("ProgramFiles", "C:\\Program Files")
PROGRAMFILES_X86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")


def _expand(path: str) -> str:
    return os.path.expandvars(path)


# Apps conocidas:
#   - aliases: lista de palabras que disparan esta app (espanol e ingles)
#   - search: texto a buscar en Start Menu Search (estrategia #1)
#   - protocol: comando con URI/protocolo si tiene (estrategia #2). None si no aplica.
#   - paths: lista de paths absolutos posibles (estrategia #3)
#   - process: nombre del proceso (.exe sin extension) para verificacion + cierre
#   - window_title: substring que debe aparecer en titulo de ventana al abrir
KNOWN_APPS: list[dict] = [
    {
        "aliases": ["telegram"],
        "search": "telegram",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\Programs\Telegram Desktop\Telegram.exe")],
        "process": "Telegram",
        "window_title": "telegram",
    },
    {
        "aliases": ["discord"],
        "search": "discord",
        "protocol": "discord:",
        "paths": [
            _expand(r"%LOCALAPPDATA%\Discord\Update.exe"),
        ],
        "protocol_args_for_path": ["--processStart", "Discord.exe"],
        "process": "Discord",
        "window_title": "discord",
    },
    {
        "aliases": ["spotify", "musica", "music"],
        "search": "spotify",
        "protocol": "spotify:",
        "paths": [
            _expand(r"%APPDATA%\Spotify\Spotify.exe"),
            _expand(r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe"),
        ],
        "process": "Spotify",
        "window_title": "spotify",
    },
    {
        "aliases": ["chrome", "google chrome", "navegador"],
        "search": "chrome",
        "protocol": None,
        "paths": [
            os.path.join(PROGRAMFILES, "Google\\Chrome\\Application\\chrome.exe"),
            os.path.join(PROGRAMFILES_X86, "Google\\Chrome\\Application\\chrome.exe"),
        ],
        "process": "chrome",
        "window_title": "chrome",
    },
    {
        "aliases": ["firefox"],
        "search": "firefox",
        "protocol": None,
        "paths": [os.path.join(PROGRAMFILES, "Mozilla Firefox\\firefox.exe")],
        "process": "firefox",
        "window_title": "firefox",
    },
    {
        "aliases": ["brave"],
        "search": "brave",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe")],
        "process": "brave",
        "window_title": "brave",
    },
    {
        "aliases": ["edge", "microsoft edge"],
        "search": "edge",
        "protocol": "microsoft-edge:",
        "paths": [os.path.join(PROGRAMFILES_X86, "Microsoft\\Edge\\Application\\msedge.exe")],
        "process": "msedge",
        "window_title": "edge",
    },
    {
        "aliases": ["opera", "opera gx"],
        "search": "opera",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe")],
        "process": "opera",
        "window_title": "opera",
    },
    {
        "aliases": ["vscode", "visual studio code", "code", "editor"],
        "search": "visual studio code",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")],
        "process": "Code",
        "window_title": "visual studio code",
    },
    {
        "aliases": ["obsidian", "vault", "cerebro", "notas"],
        "search": "obsidian",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\Obsidian\Obsidian.exe")],
        "process": "Obsidian",
        "window_title": "obsidian",
    },
    {
        "aliases": ["notion"],
        "search": "notion",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\Programs\Notion\Notion.exe")],
        "process": "Notion",
        "window_title": "notion",
    },
    {
        "aliases": ["slack"],
        "search": "slack",
        "protocol": None,
        "paths": [_expand(r"%LOCALAPPDATA%\slack\slack.exe")],
        "process": "slack",
        "window_title": "slack",
    },
    {
        "aliases": ["teams", "microsoft teams"],
        "search": "teams",
        "protocol": "msteams:",
        "paths": [_expand(r"%LOCALAPPDATA%\Programs\Teams\current\Teams.exe")],
        "process": "Teams",
        "window_title": "teams",
    },
    {
        "aliases": ["zoom"],
        "search": "zoom",
        "protocol": "zoommtg:",
        "paths": [_expand(r"%APPDATA%\Zoom\bin\Zoom.exe")],
        "process": "Zoom",
        "window_title": "zoom",
    },
    {
        "aliases": ["steam"],
        "search": "steam",
        "protocol": "steam:",
        "paths": [os.path.join(PROGRAMFILES_X86, "Steam\\steam.exe")],
        "process": "steam",
        "window_title": "steam",
    },
    {
        "aliases": ["explorer", "explorador", "archivos", "carpetas", "files"],
        "search": "explorer",
        "protocol": None,
        "paths": ["explorer.exe"],
        "process": "explorer",
        "window_title": None,  # explorer no tiene titulo distintivo
    },
    {
        "aliases": ["terminal", "cmd"],
        "search": "cmd",
        "protocol": None,
        "paths": ["cmd.exe"],
        "process": "cmd",
        "window_title": None,
    },
    {
        "aliases": ["powershell", "ps"],
        "search": "powershell",
        "protocol": None,
        "paths": ["powershell.exe"],
        "process": "powershell",
        "window_title": None,
    },
    {
        "aliases": ["notepad", "bloc de notas"],
        "search": "notepad",
        "protocol": None,
        "paths": ["notepad.exe"],
        "process": "notepad",
        "window_title": "notepad",
    },
    {
        "aliases": ["calculadora", "calc", "calculator"],
        "search": "calculadora",
        "protocol": None,
        "paths": ["calc.exe"],
        "process": "Calculator",
        "window_title": "calculadora",
    },
    {
        "aliases": ["paint", "mspaint"],
        "search": "paint",
        "protocol": None,
        "paths": ["mspaint.exe"],
        "process": "mspaint",
        "window_title": "paint",
    },
    {
        "aliases": ["task manager", "administrador de tareas", "taskmgr"],
        "search": "task manager",
        "protocol": None,
        "paths": ["taskmgr.exe"],
        "process": "Taskmgr",
        "window_title": "tareas",
    },
    {
        "aliases": ["configuracion", "settings", "ajustes"],
        "search": "configuracion",
        "protocol": "ms-settings:",
        "paths": [],
        "process": "SystemSettings",
        "window_title": None,
    },
]


# ============================================================================
# Resolución del registro applicacion
# ============================================================================

def _find_app_record(query: str) -> dict | None:
    """Busca un registro de app por alias (case-insensitive, partial match)."""
    q = query.lower().strip()
    # Match exacto primero
    for app in KNOWN_APPS:
        if q in [a.lower() for a in app["aliases"]]:
            return app
    # Substring
    for app in KNOWN_APPS:
        for alias in app["aliases"]:
            if q in alias.lower() or alias.lower() in q:
                return app
    return None


# ============================================================================
# Verificacion: ¿la app esta corriendo o tiene ventana abierta?
# ============================================================================

def _is_app_running(app: dict) -> bool:
    """Verifica si una app esta corriendo via psutil + pygetwindow."""
    process_name = app.get("process", "").lower()
    window_title = (app.get("window_title") or "").lower()

    # 1. Process check (mas robusto)
    if HAS_PSUTIL and process_name:
        try:
            for proc in psutil.process_iter(["name"]):
                pname = (proc.info.get("name") or "").lower()
                if process_name in pname or pname.startswith(process_name):
                    return True
        except Exception:
            pass

    # 2. Window check (fallback)
    if HAS_PYGETWINDOW and window_title:
        try:
            for w in gw.getAllWindows():
                if w.title and window_title in w.title.lower():
                    return True
        except Exception:
            pass

    return False


# ============================================================================
# Estrategias de apertura (5 cascada)
# ============================================================================

def _try_start_menu_search(search_term: str) -> bool:
    """Estrategia 1: tecla Windows + escribir + Enter (humano)."""
    if not HAS_PYAUTOGUI:
        return False
    try:
        pyautogui.press("win")
        time.sleep(0.6)
        pyautogui.typewrite(search_term, interval=0.04)
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1.5)  # dar tiempo a que la app arranque
        return True
    except Exception:
        return False


def _try_protocol(app: dict) -> bool:
    """Estrategia 2: URI/protocol via os.startfile o `start`."""
    proto = app.get("protocol")
    if not proto:
        return False
    try:
        # Para apps tipo Discord que necesitan args con el path:
        if app.get("protocol_args_for_path") and app.get("paths"):
            for p in app["paths"]:
                if Path(p).exists():
                    args = [p] + app["protocol_args_for_path"]
                    subprocess.Popen(args, shell=False)
                    time.sleep(1.5)
                    return True
        os.startfile(proto)
        time.sleep(1.5)
        return True
    except Exception:
        return False


def _try_known_paths(app: dict) -> bool:
    """Estrategia 3: subprocess.Popen con paths absolutos del catalogo."""
    for path in app.get("paths", []):
        try:
            # Si es solo un .exe en PATH (cmd, notepad, calc), shutil.which resuelve
            resolved = shutil.which(path) if not os.path.isabs(path) else path
            if resolved and Path(resolved).exists():
                subprocess.Popen([resolved], shell=False)
                time.sleep(1.5)
                return True
            elif Path(path).exists():
                subprocess.Popen([path], shell=False)
                time.sleep(1.5)
                return True
        except Exception:
            continue
    return False


def _try_app_paths_registry(name: str) -> bool:
    """Estrategia 4: HKLM App Paths registry."""
    try:
        import winreg
        candidates = [name, f"{name}.exe"]
        for cand in candidates:
            try:
                key_path = (
                    rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{cand}"
                )
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    value, _ = winreg.QueryValueEx(key, "")
                    if value and Path(value).exists():
                        subprocess.Popen([value], shell=False)
                        time.sleep(1.5)
                        return True
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return False


def _try_walk_search(name: str) -> bool:
    """Estrategia 5 (ultimo recurso): buscar .exe en rutas tipicas."""
    target = f"{name.lower()}.exe"
    search_roots = [
        _expand(r"%LOCALAPPDATA%\Programs"),
        _expand(r"%LOCALAPPDATA%"),
        _expand(r"%APPDATA%"),
        PROGRAMFILES,
        PROGRAMFILES_X86,
    ]
    for root in search_roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for dirpath, dirs, files in os.walk(root):
                # No descender mas de 3 niveles para no tardar eternidades
                rel_depth = dirpath[len(root):].count(os.sep)
                if rel_depth > 3:
                    dirs[:] = []
                    continue
                for f in files:
                    if f.lower() == target:
                        full = os.path.join(dirpath, f)
                        try:
                            subprocess.Popen([full], shell=False)
                            time.sleep(1.5)
                            return True
                        except Exception:
                            continue
        except Exception:
            continue
    return False


# ============================================================================
# API publica — open_app con cascada y "no se rinde"
# ============================================================================

async def open_app(app_name: str, max_attempts: int = 5) -> dict:
    """Abre una aplicacion siguiendo cascada de 5 estrategias hasta lograrlo.

    Politica: "No me detengo hasta tenerlo". Cada estrategia se verifica con
    psutil/pygetwindow para confirmar exito antes de pasar a la siguiente.

    Returns dict con:
        success: bool
        message: str (que se logro)
        attempts: list[dict] (log de cada estrategia probada)
        strategy: str | None (cual gano)
    """
    app_query = app_name.strip()
    app = _find_app_record(app_query)
    attempts = []

    # Si ya esta corriendo, exito inmediato (idempotente)
    if app and _is_app_running(app):
        # Traer al frente si tenemos pygetwindow
        if HAS_PYGETWINDOW and app.get("window_title"):
            try:
                wins = [
                    w for w in gw.getAllWindows()
                    if w.title and app["window_title"].lower() in w.title.lower()
                ]
                if wins:
                    wins[0].activate()
            except Exception:
                pass
        return {
            "success": True,
            "message": f"{app_name} ya estaba abierta — la traje al frente",
            "attempts": [],
            "strategy": "already_running",
        }

    # Determinar termino de busqueda (si no esta en catalogo, usar el nombre tal cual)
    search_term = app["search"] if app else app_query

    # Cascada
    strategies: list[tuple[str, Callable[[], bool]]] = [
        ("start_menu_search", lambda: _try_start_menu_search(search_term)),
    ]
    if app:
        strategies.append(("protocol", lambda: _try_protocol(app)))
        strategies.append(("known_paths", lambda: _try_known_paths(app)))
    strategies.append(("registry_app_paths", lambda: _try_app_paths_registry(search_term)))
    strategies.append(("walk_search", lambda: _try_walk_search(search_term)))

    for strategy_name, fn in strategies[:max_attempts]:
        attempt_log = {"strategy": strategy_name, "executed": False, "verified": False}
        try:
            executed = fn()
            attempt_log["executed"] = bool(executed)
        except Exception as e:
            attempt_log["error"] = str(e)
            attempts.append(attempt_log)
            continue

        if executed and app:
            # Verificar que efectivamente esta corriendo
            for _ in range(6):  # ~3s total
                await asyncio.sleep(0.5)
                if _is_app_running(app):
                    attempt_log["verified"] = True
                    attempts.append(attempt_log)
                    return {
                        "success": True,
                        "message": f"{app_name} abierta via {strategy_name}",
                        "attempts": attempts,
                        "strategy": strategy_name,
                    }

        # Si no hay catalogo, asumimos exito si executed=True (no podemos verificar)
        if executed and not app:
            attempts.append(attempt_log)
            return {
                "success": True,
                "message": f"Intentando abrir {app_name} via {strategy_name}",
                "attempts": attempts,
                "strategy": strategy_name,
            }

        attempts.append(attempt_log)

    return {
        "success": False,
        "error": f"No pude abrir {app_name} despues de {len(attempts)} intentos",
        "attempts": attempts,
        "strategy": None,
    }


async def close_app(app_name: str) -> dict:
    """Cierra una aplicacion. Tambien reusa el catalogo KNOWN_APPS."""
    app = _find_app_record(app_name)
    process = app["process"] if app else app_name.strip()
    proc_exe = process if process.lower().endswith(".exe") else f"{process}.exe"
    try:
        result = subprocess.run(
            ["taskkill", "/IM", proc_exe, "/F"],
            capture_output=True, text=True, timeout=8,
        )
        if result.returncode == 0:
            return {"success": True, "message": f"{app_name} cerrada"}
        return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# Acciones de sistema (volumen, brillo, screenshot, info hardware)
# ============================================================================

async def system_action(action: str) -> dict:
    """Acciones del sistema: volumen, screenshot, info hardware, etc.

    Politica: por seguridad no apaga ni reinicia automatico — solo bloquear OK.
    """
    action_lower = action.lower().strip()

    if any(w in action_lower for w in ["apagar", "shutdown", "apaga"]):
        return {
            "success": False,
            "message": "Por seguridad no apago la PC. Si quieres forzarlo, dime 'apaga forzado'.",
        }
    if "apaga forzado" in action_lower or "shutdown force" in action_lower:
        subprocess.Popen(["shutdown", "/s", "/t", "30"], shell=False)
        return {"success": True, "message": "Apagando en 30s. Cancela con: shutdown /a"}

    if any(w in action_lower for w in ["reiniciar", "restart"]):
        return {
            "success": False,
            "message": "Por seguridad no reinicio. Si quieres forzarlo, dime 'reinicia forzado'.",
        }
    if "reinicia forzado" in action_lower:
        subprocess.Popen(["shutdown", "/r", "/t", "30"], shell=False)
        return {"success": True, "message": "Reiniciando en 30s. Cancela con: shutdown /a"}

    if any(w in action_lower for w in ["bloquear", "lock", "bloquea"]):
        subprocess.Popen(
            ["rundll32.exe", "user32.dll,LockWorkStation"], shell=False,
        )
        return {"success": True, "message": "PC bloqueada"}

    if any(w in action_lower for w in ["volumen", "volume", "sube", "baja", "mute", "silencio"]):
        if any(w in action_lower for w in ["sube", "subir", "up", "mas"]):
            for _ in range(5):  # 5 toques = ~10%
                _send_vk(0xAF)  # VK_VOLUME_UP
            return {"success": True, "message": "Volumen subido"}
        if any(w in action_lower for w in ["baja", "bajar", "down", "menos"]):
            for _ in range(5):
                _send_vk(0xAE)  # VK_VOLUME_DOWN
            return {"success": True, "message": "Volumen bajado"}
        if any(w in action_lower for w in ["mute", "silencio", "silencia"]):
            _send_vk(0xAD)  # VK_VOLUME_MUTE
            return {"success": True, "message": "Volumen muteado/desmuteado"}

    if any(w in action_lower for w in ["screenshot", "captura", "pantallazo"]):
        # Win+Shift+S abre la herramienta moderna de Snipping Tool
        if HAS_PYAUTOGUI:
            pyautogui.hotkey("win", "shift", "s")
            return {"success": True, "message": "Snipping Tool abierto (Win+Shift+S)"}
        subprocess.Popen(["snippingtool.exe"], shell=False)
        return {"success": True, "message": "Snipping Tool abierto"}

    if any(w in action_lower for w in ["wifi", "red", "internet"]):
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True,
        )
        return {"success": True, "message": result.stdout[:800]}

    if any(w in action_lower for w in ["bateria", "battery"]):
        try:
            if HAS_PSUTIL:
                bat = psutil.sensors_battery()
                if bat:
                    return {
                        "success": True,
                        "message": f"Bateria: {bat.percent:.0f}% "
                                  f"({'cargando' if bat.power_plugged else 'descargando'})",
                    }
        except Exception:
            pass
        return {"success": False, "message": "No detecte bateria (PC desktop?)"}

    if any(w in action_lower for w in ["disco", "espacio", "storage"]):
        if HAS_PSUTIL:
            lines = []
            for d in psutil.disk_partitions(all=False):
                try:
                    u = psutil.disk_usage(d.mountpoint)
                    lines.append(
                        f"{d.device}: {u.used/1e9:.0f}/{u.total/1e9:.0f} GB "
                        f"({u.percent:.0f}% usado)"
                    )
                except Exception:
                    continue
            return {"success": True, "message": "\n".join(lines)}

    if any(w in action_lower for w in ["ram", "memoria"]):
        if HAS_PSUTIL:
            v = psutil.virtual_memory()
            return {
                "success": True,
                "message": f"RAM: {v.used/1e9:.1f}/{v.total/1e9:.1f} GB ({v.percent:.0f}%)",
            }

    if "procesos" in action_lower or "top" in action_lower:
        if HAS_PSUTIL:
            procs = sorted(
                psutil.process_iter(["name", "memory_info"]),
                key=lambda p: (p.info.get("memory_info").rss if p.info.get("memory_info") else 0),
                reverse=True,
            )[:10]
            lines = [
                f"{p.info['name']}: {p.info['memory_info'].rss/1e6:.0f} MB"
                for p in procs if p.info.get("memory_info")
            ]
            return {"success": True, "message": "\n".join(lines)}

    return {"success": False, "error": f"No entendi la accion: {action}"}


def _send_vk(code: int):
    """Envia una tecla virtual de Windows (volumen, etc) sin abrir powershell."""
    try:
        import ctypes
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(code, 0, 2, 0)
    except Exception:
        pass


# ============================================================================
# Helpers: URLs y carpetas
# ============================================================================

async def open_url(url: str) -> dict:
    """Abre una URL en el navegador por defecto."""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        os.startfile(url)
        return {"success": True, "message": f"Abriendo {url}"}
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
            return {"success": True, "message": f"Abriendo {url}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


async def open_folder(path: str) -> dict:
    """Abre una carpeta en el explorador de Windows."""
    expanded = os.path.expandvars(os.path.expanduser(path))
    if not os.path.exists(expanded):
        return {"success": False, "error": f"Carpeta no existe: {expanded}"}
    try:
        subprocess.Popen(["explorer", expanded], shell=False)
        return {"success": True, "message": f"Abriendo {expanded}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# CLI rapido para test manual
# ============================================================================

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python pc_control.py <app_name>")
        sys.exit(1)
    target = " ".join(sys.argv[1:])
    print(f"Abriendo {target}...")
    result = asyncio.run(open_app(target))
    print(result)
