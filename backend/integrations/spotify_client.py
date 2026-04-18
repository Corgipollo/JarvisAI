"""Spotify — control basico via comandos del sistema.
Para control avanzado, configurar SPOTIFY_CLIENT_ID en .env."""
import subprocess
import asyncio


async def spotify_play() -> dict:
    """Play/Resume."""
    subprocess.Popen(
        'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]179)"',
        shell=True,
    )
    return {"success": True, "message": "Play/Pause Spotify"}


async def spotify_next() -> dict:
    """Siguiente cancion."""
    subprocess.Popen(
        'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]176)"',
        shell=True,
    )
    return {"success": True, "message": "Siguiente cancion"}


async def spotify_previous() -> dict:
    """Cancion anterior."""
    subprocess.Popen(
        'powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]177)"',
        shell=True,
    )
    return {"success": True, "message": "Cancion anterior"}


async def spotify_action(action: str) -> dict:
    """Ejecuta accion de Spotify."""
    action_lower = action.lower()

    if any(w in action_lower for w in ["play", "reproduce", "pon", "ponme", "toca", "dale"]):
        return await spotify_play()
    elif any(w in action_lower for w in ["pausa", "pause", "para", "stop", "detente"]):
        return await spotify_play()  # Toggle play/pause
    elif any(w in action_lower for w in ["siguiente", "next", "skip", "cambia", "otra"]):
        return await spotify_next()
    elif any(w in action_lower for w in ["anterior", "previous", "atras", "regresa"]):
        return await spotify_previous()
    elif any(w in action_lower for w in ["abre", "abrir", "open"]):
        subprocess.Popen("start spotify:", shell=True)
        return {"success": True, "message": "Abriendo Spotify"}

    return {"success": False, "error": f"No entendi: {action}. Prueba: play, pausa, siguiente, anterior."}
