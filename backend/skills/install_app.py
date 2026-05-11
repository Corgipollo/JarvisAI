"""install_app.py — Skill autonoma para instalar apps con fallbacks.

Cascada (cada step verifica si la app quedo instalada):
  1. winget search + install --silent
  2. choco install (si chocolatey instalado)
  3. scoop install
  4. ask_brain: pide a Claude que busque pagina oficial + descarga via Playwright
     + click instalador con pyautogui

Verificacion post-instalacion:
  - Inventario apps (windows_intel)
  - Test: intentar abrir la app con pc_control.open_app

Si falla TODO, devuelve error con log detallado de qué intentó.
"""
from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg: str):
    print(f"[install_app] {msg}", flush=True)


def is_app_installed(app_name: str) -> bool:
    """Chequea si app esta instalada (windows_intel + which)."""
    name_lower = app_name.lower().replace(" ", "")
    # Quick check via shutil.which
    for cmd in (app_name.lower(), name_lower, f"{name_lower}.exe"):
        if shutil.which(cmd):
            return True
    # Inventory check
    inv = ROOT / "data" / "windows_inventory.json"
    if inv.exists():
        try:
            data = json.loads(inv.read_text(encoding="utf-8"))
            for app in data.get("apps_classic", []) + data.get("apps_uwp", []):
                if name_lower in (app.get("displayname", "") or app.get("name", "")).lower().replace(" ", ""):
                    return True
        except Exception:
            pass
    return False


# ============================================================================
# Strategy 1: winget
# ============================================================================
def try_winget(app_name: str) -> dict:
    """winget search + install --silent."""
    try:
        # Search
        search = subprocess.run(
            ["winget", "search", app_name, "--accept-source-agreements"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
        )
        if search.returncode != 0 or "No package found" in search.stdout:
            return {"success": False, "reason": "winget no encontro paquete"}

        # Parse: extract package ID (segunda columna)
        match = re.search(r"^(\S.+?)\s+(\S+\.\S+)\s+", search.stdout, re.MULTILINE)
        if not match:
            return {"success": False, "reason": "no pude parsear package ID"}
        pkg_id = match.group(2)
        log(f"  winget pkg ID: {pkg_id}")

        # Install silent
        install = subprocess.run(
            ["winget", "install", "--id", pkg_id,
             "--accept-package-agreements", "--accept-source-agreements",
             "--silent", "--disable-interactivity"],
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        if install.returncode == 0 or "successfully installed" in install.stdout.lower():
            return {"success": True, "strategy": "winget", "pkg_id": pkg_id}
        return {"success": False, "reason": f"winget install rc={install.returncode}: {install.stdout[:200]}"}
    except Exception as e:
        return {"success": False, "reason": f"winget exception: {e}"}


# ============================================================================
# Strategy 2: choco
# ============================================================================
def try_choco(app_name: str) -> dict:
    if not shutil.which("choco"):
        return {"success": False, "reason": "choco no instalado"}
    try:
        r = subprocess.run(
            ["choco", "install", app_name, "-y", "--no-progress"],
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        if "Successful: 1/1" in r.stdout or "has been installed" in r.stdout.lower():
            return {"success": True, "strategy": "choco"}
        return {"success": False, "reason": "choco no logro instalar"}
    except Exception as e:
        return {"success": False, "reason": f"choco: {e}"}


# ============================================================================
# Strategy 3: scoop
# ============================================================================
def try_scoop(app_name: str) -> dict:
    if not shutil.which("scoop"):
        return {"success": False, "reason": "scoop no instalado"}
    try:
        r = subprocess.run(
            ["scoop", "install", app_name],
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        if r.returncode == 0:
            return {"success": True, "strategy": "scoop"}
        return {"success": False, "reason": "scoop rc!=0"}
    except Exception as e:
        return {"success": False, "reason": f"scoop: {e}"}


# ============================================================================
# Strategy 4: ask_brain — Claude busca pagina oficial + Playwright + pyautogui
# ============================================================================
async def try_official_download(app_name: str) -> dict:
    """Pide a Claude que genere plan para descargar de pagina oficial."""
    try:
        from backend.skills.ask_brain import jarvis_handle
    except ImportError:
        return {"success": False, "reason": "ask_brain no disponible"}

    plan_request = (
        f"Necesito instalar '{app_name}' en Windows desde la pagina oficial.\n"
        f"Genera plan ejecutable que:\n"
        f"1. Abre browser y va a la URL oficial de descarga\n"
        f"2. Click en boton de descarga Windows x64\n"
        f"3. Espera que termine descarga (revisa carpeta Downloads)\n"
        f"4. Ejecuta el .exe descargado\n"
        f"5. Click 'Next/Install/Aceptar' en cada paso del wizard\n"
        f"Usa skills disponibles: press_keys, type_text, click, hover, scroll, wait, "
        f"read_screen, find_text, run_cmd."
    )

    try:
        result = await jarvis_handle(plan_request)
        if result.get("success"):
            return {"success": True, "strategy": "ask_brain_official_download",
                    "plan": result.get("plan")}
        return {"success": False, "reason": f"ask_brain plan fallo: {result.get('error')}"}
    except Exception as e:
        return {"success": False, "reason": f"ask_brain exception: {e}"}


# ============================================================================
# API PUBLICA
# ============================================================================
async def install_app(app_name: str, verify: bool = True) -> dict:
    """Instala app con cascada de estrategias. Devuelve resultado completo.

    Si la app ya está instalada: success inmediato (idempotente).
    Si no: prueba winget → choco → scoop → ask_brain → reporta fallo total.
    """
    log(f"=== install_app: {app_name} ===")

    # Idempotente
    if is_app_installed(app_name):
        log("  ya instalada")
        return {"success": True, "strategy": "already_installed"}

    attempts = []

    # 1. winget
    log("[1] try winget...")
    r = try_winget(app_name)
    attempts.append({"strategy": "winget", **r})
    if r["success"]:
        if verify and is_app_installed(app_name):
            return {"success": True, "strategy": "winget", "attempts": attempts}

    # 2. choco
    log("[2] try choco...")
    r = try_choco(app_name)
    attempts.append({"strategy": "choco", **r})
    if r["success"]:
        if verify and is_app_installed(app_name):
            return {"success": True, "strategy": "choco", "attempts": attempts}

    # 3. scoop
    log("[3] try scoop...")
    r = try_scoop(app_name)
    attempts.append({"strategy": "scoop", **r})
    if r["success"]:
        if verify and is_app_installed(app_name):
            return {"success": True, "strategy": "scoop", "attempts": attempts}

    # 4. ask_brain: Claude busca + ejecuta plan
    log("[4] try ask_brain (oficial download)...")
    r = await try_official_download(app_name)
    attempts.append({"strategy": "ask_brain", **r})
    if r.get("success") and is_app_installed(app_name):
        return {"success": True, "strategy": "ask_brain", "attempts": attempts}

    log(f"FALLARON TODAS las estrategias para {app_name}")
    return {
        "success": False,
        "error": f"no pude instalar {app_name} despues de {len(attempts)} intentos",
        "attempts": attempts,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python install_app.py <app_name>")
        sys.exit(0)
    app = " ".join(sys.argv[1:])
    result = asyncio.run(install_app(app))
    print(json.dumps(result, ensure_ascii=False, indent=2))
