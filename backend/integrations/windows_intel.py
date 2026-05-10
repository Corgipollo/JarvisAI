r"""
windows_intel.py — Scanner profundo del sistema Windows para Jarvis.

================================================================================
PROPOSITO
================================================================================

Jarvis debe TENER EL CONOCIMIENTO COMPLETO de la PC de Emmanuel: que apps tiene
instaladas, donde estan, que paths usan, que hay pinneado al taskbar, hardware,
red, servicios, todo.

Este modulo escanea TODO y guarda el resultado en
`JarvisAI/data/windows_inventory.json`. Despues `pc_control.open_app()` puede
leer ese inventory para resolver paths reales en vez de adivinar.

================================================================================
QUE ESCANEA
================================================================================

1. **Apps instaladas (classic)** — Registry HKLM + HKCU `Uninstall` keys.
   Da: nombre, version, install_location, uninstall_string, publisher.

2. **Apps UWP/Microsoft Store** — `Get-AppxPackage` PowerShell.
   Da: name, package_family_name, install_location, version.

3. **App Paths** — Registry HKLM `App Paths`. Mapeo nombre.exe → path absoluto.

4. **Taskbar pineado** — directorio
   `%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar`.
   Da: lista ordenada de .lnk con sus targets reales.

5. **Start Menu** — directorio user + system con .lnk shortcuts.
   Da: nombre + target del shortcut.

6. **Hardware** — psutil: CPU, RAM, disks, GPUs (via wmi si disponible).

7. **Red** — interfaces, IPs, gateway, WiFi SSID actual.

8. **Servicios Windows** — Win32_Service via WMI: nombre, estado, startup.

9. **Default apps** — file associations (browser, email, video, etc.).

10. **Sistema** — version Windows, hostname, user, idioma, timezone, uptime.

================================================================================
USO
================================================================================

```python
from windows_intel import scan_all, save_inventory, load_inventory

# Una vez (al setup o cron diario):
inv = scan_all()
save_inventory(inv)

# Despues, en cualquier modulo:
inv = load_inventory()
chrome_path = inv["app_paths"].get("chrome.exe")
pinned = inv["taskbar_pinned"]
ssid = inv["network"]["wifi_ssid"]
```

CLI:
```bash
python backend/integrations/windows_intel.py        # full scan
python backend/integrations/windows_intel.py apps   # solo apps
python backend/integrations/windows_intel.py hw     # solo hardware
```
"""
from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import winreg
    HAS_WINREG = True
except ImportError:
    HAS_WINREG = False

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
INVENTORY_FILE = DATA_DIR / "windows_inventory.json"


# ============================================================================
# Apps classic via Registry Uninstall keys
# ============================================================================

def scan_installed_apps_classic() -> list[dict]:
    """Lee Uninstall keys de HKLM (32+64) y HKCU."""
    if not HAS_WINREG:
        return []
    apps: dict[str, dict] = {}
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, root in keys:
        try:
            with winreg.OpenKey(hive, root) as parent:
                i = 0
                while True:
                    try:
                        sub = winreg.EnumKey(parent, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(parent, sub) as k:
                            entry: dict[str, Any] = {"key": sub}
                            for vname in (
                                "DisplayName", "DisplayVersion", "Publisher",
                                "InstallLocation", "InstallDate",
                                "UninstallString", "DisplayIcon",
                            ):
                                try:
                                    val, _ = winreg.QueryValueEx(k, vname)
                                    entry[vname.lower()] = val
                                except FileNotFoundError:
                                    continue
                            if entry.get("displayname"):
                                key = entry["displayname"].lower()
                                if key not in apps:
                                    apps[key] = entry
                    except OSError:
                        continue
        except FileNotFoundError:
            continue
    return list(apps.values())


def scan_app_paths() -> dict[str, str]:
    """HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\App Paths.

    Mapeo nombre.exe → path absoluto. Es lo que usa el comando `start` interno.
    """
    if not HAS_WINREG:
        return {}
    result: dict[str, str] = {}
    paths_to_scan = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
    ]
    for hive, base in paths_to_scan:
        try:
            with winreg.OpenKey(hive, base) as parent:
                i = 0
                while True:
                    try:
                        name = winreg.EnumKey(parent, i)
                        i += 1
                    except OSError:
                        break
                    try:
                        with winreg.OpenKey(parent, name) as k:
                            val, _ = winreg.QueryValueEx(k, "")
                            if val and Path(val.strip('"')).exists():
                                result[name.lower()] = val.strip('"')
                    except OSError:
                        continue
        except FileNotFoundError:
            continue
    return result


# ============================================================================
# Apps UWP / Microsoft Store
# ============================================================================

def scan_installed_apps_uwp() -> list[dict]:
    """`Get-AppxPackage` via PowerShell."""
    try:
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-Command",
                "Get-AppxPackage | Select-Object Name,PackageFamilyName,Version,InstallLocation | ConvertTo-Json -Compress",
            ],
            capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            return []
        data = json.loads(proc.stdout) if proc.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        return [
            {
                "name": d.get("Name", ""),
                "package_family_name": d.get("PackageFamilyName", ""),
                "version": d.get("Version", ""),
                "install_location": d.get("InstallLocation", ""),
            }
            for d in data
        ]
    except Exception:
        return []


# ============================================================================
# Taskbar pineado
# ============================================================================

def scan_taskbar_pinned() -> list[dict]:
    """Lista los .lnk pineados al taskbar y resuelve sus targets."""
    pinned_dir = Path(os.environ.get("APPDATA", "")) / (
        "Microsoft/Internet Explorer/Quick Launch/User Pinned/TaskBar"
    )
    if not pinned_dir.is_dir():
        return []
    items = []
    for lnk in sorted(pinned_dir.glob("*.lnk")):
        target = _resolve_lnk(lnk)
        items.append({
            "name": lnk.stem,
            "lnk": str(lnk),
            "target": target,
        })
    return items


def scan_start_menu() -> list[dict]:
    """Recorre Start Menu (user + system) y devuelve shortcuts con target."""
    roots = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    items = []
    for root in roots:
        if not root.is_dir():
            continue
        for lnk in root.rglob("*.lnk"):
            try:
                target = _resolve_lnk(lnk)
                items.append({
                    "name": lnk.stem,
                    "category": str(lnk.parent.relative_to(root)),
                    "lnk": str(lnk),
                    "target": target,
                })
            except Exception:
                continue
    return items


def _resolve_lnk(path: Path) -> str:
    """Resuelve un .lnk a su path target via Shell COM."""
    try:
        import pythoncom  # type: ignore
        from win32com.client import Dispatch  # type: ignore
        pythoncom.CoInitialize()
        try:
            shell = Dispatch("WScript.Shell")
            sc = shell.CreateShortCut(str(path))
            return sc.Targetpath
        finally:
            pythoncom.CoUninitialize()
    except Exception:
        # Fallback: PowerShell
        try:
            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-Command",
                    f"(New-Object -COM WScript.Shell).CreateShortcut('{path}').TargetPath",
                ],
                capture_output=True, text=True, timeout=10,
            )
            return proc.stdout.strip()
        except Exception:
            return ""


# ============================================================================
# Hardware
# ============================================================================

def scan_hardware() -> dict:
    """CPU, RAM, disks, GPU (basico)."""
    out: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
    }
    if HAS_PSUTIL:
        out["cpu"] = {
            "physical_cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "max_freq_mhz": getattr(psutil.cpu_freq(), "max", None),
        }
        v = psutil.virtual_memory()
        out["ram"] = {
            "total_gb": round(v.total / 1e9, 1),
            "available_gb": round(v.available / 1e9, 1),
            "percent_used": v.percent,
        }
        out["disks"] = []
        for d in psutil.disk_partitions(all=False):
            try:
                u = psutil.disk_usage(d.mountpoint)
                out["disks"].append({
                    "device": d.device,
                    "mountpoint": d.mountpoint,
                    "fstype": d.fstype,
                    "total_gb": round(u.total / 1e9, 1),
                    "used_gb": round(u.used / 1e9, 1),
                    "free_gb": round(u.free / 1e9, 1),
                    "percent_used": u.percent,
                })
            except Exception:
                continue

    # GPU via WMI (opcional)
    try:
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion,AdapterRAM | ConvertTo-Json -Compress",
            ],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            if isinstance(data, dict):
                data = [data]
            out["gpus"] = [
                {
                    "name": d.get("Name", ""),
                    "driver": d.get("DriverVersion", ""),
                    "vram_gb": round((d.get("AdapterRAM") or 0) / 1e9, 1),
                }
                for d in data
            ]
    except Exception:
        out["gpus"] = []

    return out


# ============================================================================
# Red
# ============================================================================

def scan_network() -> dict:
    out: dict[str, Any] = {"hostname": socket.gethostname()}
    if HAS_PSUTIL:
        out["interfaces"] = {}
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        for name, addr_list in addrs.items():
            iface = {
                "is_up": stats.get(name).isup if name in stats else False,
                "addresses": [],
            }
            for a in addr_list:
                if a.family.name in ("AF_INET", "AF_INET6"):
                    iface["addresses"].append({
                        "family": a.family.name,
                        "address": a.address,
                        "netmask": a.netmask,
                    })
            out["interfaces"][name] = iface

    # SSID actual via netsh
    try:
        proc = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"],
            capture_output=True, text=True, timeout=10,
        )
        for line in proc.stdout.splitlines():
            if "SSID" in line and "BSSID" not in line:
                out["wifi_ssid"] = line.split(":", 1)[-1].strip()
                break
    except Exception:
        pass

    return out


# ============================================================================
# Servicios Windows
# ============================================================================

def scan_services(only_running: bool = True) -> list[dict]:
    try:
        cmd = (
            "Get-CimInstance Win32_Service | "
            f"{'Where-Object State -eq Running |' if only_running else ''}"
            "Select-Object Name,DisplayName,State,StartMode | ConvertTo-Json -Compress"
        )
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", cmd],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            data = [data]
        return [
            {
                "name": d.get("Name", ""),
                "display_name": d.get("DisplayName", ""),
                "state": d.get("State", ""),
                "start_mode": d.get("StartMode", ""),
            }
            for d in data
        ]
    except Exception:
        return []


# ============================================================================
# Default apps (file associations basicas)
# ============================================================================

def scan_default_apps() -> dict[str, str]:
    """Default browser, mail, etc."""
    if not HAS_WINREG:
        return {}
    out: dict[str, str] = {}
    items = {
        "default_browser": r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice",
        "default_https": r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
        "default_pdf": r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.pdf\UserChoice",
        "default_mp4": r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.mp4\UserChoice",
        "default_mp3": r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.mp3\UserChoice",
        "default_jpg": r"Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.jpg\UserChoice",
    }
    for key_name, path in items.items():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
                val, _ = winreg.QueryValueEx(k, "ProgId")
                out[key_name] = val
        except FileNotFoundError:
            continue
    return out


# ============================================================================
# Info sistema
# ============================================================================

def scan_system_info() -> dict:
    out = {
        "hostname": socket.gethostname(),
        "user": os.environ.get("USERNAME", ""),
        "userprofile": os.environ.get("USERPROFILE", ""),
        "windows_version": platform.version(),
        "windows_release": platform.release(),
        "windows_edition": "",
        "language": "",
        "timezone": time.tzname[0] if time.tzname else "",
        "boot_time": "",
        "uptime_hours": 0.0,
    }
    if HAS_PSUTIL:
        bt = psutil.boot_time()
        out["boot_time"] = datetime.fromtimestamp(bt).isoformat()
        out["uptime_hours"] = round((time.time() - bt) / 3600, 1)

    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "(Get-ComputerInfo | Select-Object WindowsProductName,OsLanguage | ConvertTo-Json -Compress)"],
            capture_output=True, text=True, timeout=20,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout)
            out["windows_edition"] = data.get("WindowsProductName", "")
            lang = data.get("OsLanguage")
            if isinstance(lang, dict):
                out["language"] = lang.get("Name", "")
            elif isinstance(lang, str):
                out["language"] = lang
    except Exception:
        pass

    return out


# ============================================================================
# Orquestador
# ============================================================================

def scan_all(include_services: bool = True) -> dict:
    """Escaneo completo. Devuelve un dict con todo el inventario."""
    print("[windows_intel] scan: system_info...")
    sys_info = scan_system_info()
    print("[windows_intel] scan: hardware...")
    hw = scan_hardware()
    print("[windows_intel] scan: network...")
    net = scan_network()
    print("[windows_intel] scan: app_paths registry...")
    app_paths = scan_app_paths()
    print("[windows_intel] scan: installed apps classic...")
    apps_classic = scan_installed_apps_classic()
    print(f"[windows_intel]   {len(apps_classic)} apps classic encontradas")
    print("[windows_intel] scan: installed apps UWP...")
    apps_uwp = scan_installed_apps_uwp()
    print(f"[windows_intel]   {len(apps_uwp)} apps UWP encontradas")
    print("[windows_intel] scan: taskbar pinned...")
    pinned = scan_taskbar_pinned()
    print(f"[windows_intel]   {len(pinned)} apps pinned al taskbar")
    print("[windows_intel] scan: start menu shortcuts...")
    start_menu = scan_start_menu()
    print(f"[windows_intel]   {len(start_menu)} shortcuts en Start Menu")
    print("[windows_intel] scan: default apps...")
    defaults = scan_default_apps()
    services = []
    if include_services:
        print("[windows_intel] scan: services running...")
        services = scan_services(only_running=True)
        print(f"[windows_intel]   {len(services)} servicios corriendo")

    return {
        "scanned_at": datetime.now().isoformat(),
        "system": sys_info,
        "hardware": hw,
        "network": net,
        "app_paths": app_paths,
        "apps_classic": apps_classic,
        "apps_uwp": apps_uwp,
        "taskbar_pinned": pinned,
        "start_menu": start_menu,
        "default_apps": defaults,
        "services_running": services,
    }


def save_inventory(inv: dict, path: Path = INVENTORY_FILE) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[windows_intel] inventario guardado en {path} ({path.stat().st_size/1024:.0f} KB)")
    return path


def load_inventory(path: Path = INVENTORY_FILE) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ============================================================================
# Lookup helper — usado por pc_control.open_app()
# ============================================================================

# Palabras que indican que NO es la app real (uninstaller, helper, etc.)
NEGATIVE_TERMS = (
    "uninstall", "desinstalar", "remove", "uninst", "uninstaller",
    "helper", "service", "updater", "update.exe is not", "crashpad",
)

# Aliases query → search terms expandidos (mejor matching)
QUERY_ALIASES: dict[str, list[str]] = {
    "vscode": ["visual studio code", "code", "vscode"],
    "code": ["visual studio code", "code"],
    "vs code": ["visual studio code", "code"],
    "navegador": ["chrome", "brave", "edge", "firefox", "opera"],
    "musica": ["spotify", "music"],
    "music": ["spotify"],
    "editor": ["visual studio code", "notepad++", "sublime"],
    "telegram": ["telegram desktop", "telegram"],
    "discord": ["discord"],
    "store": ["microsoft store"],
    "tienda": ["microsoft store"],
    "fotos": ["photos", "fotos"],
    "video": ["video", "movies", "media player"],
}


def _is_negative_match(name: str) -> bool:
    n = name.lower()
    return any(t in n for t in NEGATIVE_TERMS)


def find_app_in_inventory(query: str, inventory: dict | None = None) -> dict | None:
    """Busca una app por nombre en el inventory real del sistema.

    Devuelve dict con {target, source, name} o None.
    Filtra desinstaladores, helpers y otros no-launchers.
    """
    if inventory is None:
        inventory = load_inventory()
    if not inventory:
        return None
    q_orig = query.lower().strip()

    # Expandir query con aliases
    queries = QUERY_ALIASES.get(q_orig, [q_orig])
    if q_orig not in queries:
        queries = [q_orig] + queries

    # 1. App Paths registry (mas confiable — es lo que usa Windows internamente)
    ap = inventory.get("app_paths", {})
    for q in queries:
        for key, target in ap.items():
            key_clean = key.lower().replace(".exe", "")
            if (q == key_clean or q in key_clean or key_clean in q) and not _is_negative_match(key):
                if Path(target).exists():
                    return {"target": target, "source": "app_paths", "name": key}

    # 2. Taskbar pinned (lo que el user usa a diario — alta prioridad)
    for q in queries:
        for item in inventory.get("taskbar_pinned", []):
            if (q in item["name"].lower() and item.get("target") and
                    not _is_negative_match(item["name"]) and
                    Path(item["target"]).exists()):
                return {"target": item["target"], "source": "taskbar", "name": item["name"]}

    # 3. Start Menu shortcuts (filtra desinstaladores)
    for q in queries:
        matches = []
        for item in inventory.get("start_menu", []):
            name = item["name"].lower()
            target = item.get("target") or ""
            if (q in name and target and target.lower().endswith(".exe") and
                    not _is_negative_match(name) and
                    not _is_negative_match(target)):
                matches.append(item)
        if matches:
            # Preferir el match mas corto en nombre (mas especifico, ej "Discord" vs "Discord PTB")
            matches.sort(key=lambda m: len(m["name"]))
            for m in matches:
                if Path(m["target"]).exists():
                    return {"target": m["target"], "source": "start_menu", "name": m["name"]}

    # 4. Apps classic con install_location (busca .exe principal en la carpeta)
    for q in queries:
        for app in inventory.get("apps_classic", []):
            name = (app.get("displayname") or "").lower()
            if q in name and not _is_negative_match(name):
                loc = app.get("installlocation") or ""
                if loc and Path(loc).is_dir():
                    # Buscar .exe que matche el query en stem
                    exes = list(Path(loc).glob("*.exe"))
                    exes_no_neg = [e for e in exes if not _is_negative_match(e.stem)]
                    # Preferir el que tenga el query en stem
                    for e in exes_no_neg:
                        if q in e.stem.lower():
                            return {"target": str(e), "source": "apps_classic", "name": app["displayname"]}
                    if exes_no_neg:
                        return {"target": str(exes_no_neg[0]), "source": "apps_classic", "name": app["displayname"]}

    # 5. Apps UWP / Microsoft Store
    for q in queries:
        for app in inventory.get("apps_uwp", []):
            name = (app.get("name") or "").lower()
            pfn = app.get("package_family_name") or ""
            if q in name and pfn and not _is_negative_match(name):
                # UWP se lanzan via shell:AppsFolder\PackageFamilyName!App
                target = f"shell:AppsFolder\\{pfn}!App"
                return {"target": target, "source": "apps_uwp", "name": name, "is_uwp": True}

    return None


# ============================================================================
# CLI
# ============================================================================

def main():
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "all":
        inv = scan_all()
        save_inventory(inv)
        print(f"\nResumen:")
        print(f"  Sistema: {inv['system']['windows_edition']} ({inv['system']['user']})")
        print(f"  CPU: {inv['hardware'].get('processor', '?')}")
        print(f"  RAM: {inv['hardware']['ram']['total_gb']} GB")
        print(f"  Apps classic: {len(inv['apps_classic'])}")
        print(f"  Apps UWP: {len(inv['apps_uwp'])}")
        print(f"  Taskbar pinned: {len(inv['taskbar_pinned'])}")
        print(f"  Start Menu shortcuts: {len(inv['start_menu'])}")
        print(f"  App Paths: {len(inv['app_paths'])}")
        print(f"  Servicios corriendo: {len(inv['services_running'])}")
    elif cmd == "apps":
        save_inventory({
            "scanned_at": datetime.now().isoformat(),
            "app_paths": scan_app_paths(),
            "apps_classic": scan_installed_apps_classic(),
            "apps_uwp": scan_installed_apps_uwp(),
            "taskbar_pinned": scan_taskbar_pinned(),
            "start_menu": scan_start_menu(),
        })
    elif cmd == "hw":
        hw = scan_hardware()
        print(json.dumps(hw, ensure_ascii=False, indent=2))
    elif cmd == "find":
        if len(sys.argv) < 3:
            print("Uso: python windows_intel.py find <app>")
            sys.exit(1)
        result = find_app_in_inventory(sys.argv[2])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Uso: python windows_intel.py [all|apps|hw|find <name>]")


if __name__ == "__main__":
    main()
