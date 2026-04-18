"""Control de PC — abrir apps, archivos, comandos del sistema."""
import subprocess
import os
import platform


# Apps conocidas y sus rutas/comandos
KNOWN_APPS = {
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "navegador": "start chrome",
    "opera": 'start "" "C:\\Users\\Emmanuel\\AppData\\Local\\Programs\\Opera GX\\opera.exe"',
    "opera gx": 'start "" "C:\\Users\\Emmanuel\\AppData\\Local\\Programs\\Opera GX\\opera.exe"',
    "vscode": "code",
    "visual studio code": "code",
    "visual studio": "code",
    "code": "code",
    "editor": "code",
    "terminal": "start cmd",
    "cmd": "start cmd",
    "powershell": "start powershell",
    "explorador": "explorer",
    "explorer": "explorer",
    "archivos": "explorer",
    "carpetas": "explorer",
    "bloc de notas": "notepad",
    "notepad": "notepad",
    "calculadora": "calc",
    "calculator": "calc",
    "spotify": "start spotify:",
    "musica": "start spotify:",
    "configuracion": "start ms-settings:",
    "settings": "start ms-settings:",
    "paint": "mspaint",
    "discord": "start discord:",
    "obsidian": 'start "" "C:\\Users\\Emmanuel\\AppData\\Local\\Obsidian\\Obsidian.exe"',
    "task manager": "taskmgr",
    "administrador de tareas": "taskmgr",
}


async def open_app(app_name: str) -> dict:
    """Abre una aplicacion por nombre."""
    app_lower = app_name.lower().strip()

    # Buscar en apps conocidas
    for key, cmd in KNOWN_APPS.items():
        if key in app_lower or app_lower in key:
            try:
                subprocess.Popen(cmd, shell=True)
                return {"success": True, "message": f"Abriendo {app_name}"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    # Si no es conocida, intentar abrir directamente
    try:
        subprocess.Popen(f"start {app_name}", shell=True)
        return {"success": True, "message": f"Intentando abrir {app_name}"}
    except Exception as e:
        return {"success": False, "error": f"No se pudo abrir {app_name}: {e}"}


async def close_app(app_name: str) -> dict:
    """Cierra una aplicacion."""
    app_lower = app_name.lower().strip()

    # Mapeo de nombre comun a nombre de proceso
    process_names = {
        "chrome": "chrome", "opera": "opera", "firefox": "firefox",
        "spotify": "Spotify", "discord": "Discord", "vscode": "Code",
        "visual studio code": "Code", "notepad": "notepad",
        "explorador": "explorer",
    }

    proc = process_names.get(app_lower, app_lower)
    try:
        result = subprocess.run(
            f"taskkill /IM {proc}.exe /F",
            shell=True, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return {"success": True, "message": f"{app_name} cerrado"}
        return {"success": False, "error": result.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def system_action(action: str) -> dict:
    """Acciones del sistema: volumen, brillo, apagar, etc."""
    action_lower = action.lower().strip()

    if any(w in action_lower for w in ["apagar", "shutdown", "apaga"]):
        return {"success": False, "message": "Por seguridad, no apago la PC automaticamente. Usa el menu de inicio."}

    elif any(w in action_lower for w in ["reiniciar", "restart"]):
        return {"success": False, "message": "Por seguridad, no reinicio automaticamente. Hazlo desde el menu de inicio."}

    elif any(w in action_lower for w in ["bloquear", "lock", "bloquea"]):
        subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
        return {"success": True, "message": "PC bloqueada"}

    elif any(w in action_lower for w in ["volumen", "volume", "sube", "baja"]):
        # Subir o bajar volumen con nircmd o PowerShell
        if any(w in action_lower for w in ["sube", "subir", "up", "mas"]):
            subprocess.Popen(
                'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"',
                shell=True
            )
            return {"success": True, "message": "Volumen subido"}
        elif any(w in action_lower for w in ["baja", "bajar", "down", "menos"]):
            subprocess.Popen(
                'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"',
                shell=True
            )
            return {"success": True, "message": "Volumen bajado"}
        elif any(w in action_lower for w in ["mute", "silencio", "silencia"]):
            subprocess.Popen(
                'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"',
                shell=True
            )
            return {"success": True, "message": "Volumen muteado"}

    elif any(w in action_lower for w in ["screenshot", "captura", "pantallazo"]):
        subprocess.Popen("snippingtool", shell=True)
        return {"success": True, "message": "Herramienta de captura abierta"}

    elif any(w in action_lower for w in ["wifi", "red", "internet"]):
        result = subprocess.run("netsh wlan show interfaces", shell=True, capture_output=True, text=True)
        return {"success": True, "message": result.stdout[:500]}

    elif any(w in action_lower for w in ["bateria", "battery"]):
        result = subprocess.run(
            'powershell -Command "(Get-WmiObject Win32_Battery).EstimatedChargeRemaining"',
            shell=True, capture_output=True, text=True,
        )
        return {"success": True, "message": f"Bateria: {result.stdout.strip()}%"}

    elif any(w in action_lower for w in ["disco", "espacio", "storage"]):
        result = subprocess.run(
            'powershell -Command "Get-PSDrive -PSProvider FileSystem | Select-Object Name,@{N=\'Used(GB)\';E={[math]::Round($_.Used/1GB,1)}},@{N=\'Free(GB)\';E={[math]::Round($_.Free/1GB,1)}} | Format-Table -AutoSize"',
            shell=True, capture_output=True, text=True,
        )
        return {"success": True, "message": result.stdout}

    elif any(w in action_lower for w in ["ram", "memoria", "procesos"]):
        result = subprocess.run(
            'powershell -Command "Get-Process | Sort-Object -Property WorkingSet64 -Descending | Select-Object -First 10 Name,@{N=\'RAM(MB)\';E={[math]::Round($_.WorkingSet64/1MB)}} | Format-Table -AutoSize"',
            shell=True, capture_output=True, text=True,
        )
        return {"success": True, "message": result.stdout}

    return {"success": False, "error": f"No entendi la accion: {action}"}


async def open_url(url: str) -> dict:
    """Abre una URL en el navegador."""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        subprocess.Popen(f'start "" "{url}"', shell=True)
        return {"success": True, "message": f"Abriendo {url}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def open_folder(path: str) -> dict:
    """Abre una carpeta en el explorador."""
    if os.path.exists(path):
        subprocess.Popen(f'explorer "{path}"', shell=True)
        return {"success": True, "message": f"Abriendo {path}"}
    return {"success": False, "error": f"Carpeta no existe: {path}"}
