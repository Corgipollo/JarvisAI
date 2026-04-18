"""Integración con Claude Code CLI — manda tareas de código a Claude."""
import subprocess
import asyncio
import os
import json
from pathlib import Path

CLAUDE_PATH = r"C:\Users\Emmanuel\AppData\Roaming\Claude\claude-code\2.1.87\claude.exe"
PROJECTS_DIR = Path(r"C:\Users\Emmanuel\Documents\JarvisAI\generated")


async def run_claude_task(task: str, callback=None) -> dict:
    """Ejecuta una tarea en Claude Code y retorna el resultado.

    Args:
        task: Descripción de lo que generar
        callback: Función async para notificar progreso
    """
    # Crear carpeta para el proyecto generado
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    # Nombre del proyecto basado en la tarea
    safe_name = "".join(c if c.isalnum() or c in "-_ " else "" for c in task[:40]).strip().replace(" ", "-").lower()
    if not safe_name:
        safe_name = "proyecto"
    project_dir = PROJECTS_DIR / safe_name
    project_dir.mkdir(parents=True, exist_ok=True)

    if callback:
        await callback(f"Trabajando en: {task[:60]}...")

    try:
        # Ejecutar Claude Code con la tarea
        prompt = f"""Crea archivos en el directorio actual ({project_dir}).
Si es pagina web: index.html + style.css + script.js.
Si es app: toda la estructura necesaria.
Archivos funcionales y completos. Sin TODOs.

Tarea: {task}"""

        process = await asyncio.create_subprocess_exec(
            CLAUDE_PATH,
            "--print",
            "--allow-dangerously-skip-permissions",
            "--dangerously-skip-permissions",
            "-p", prompt,
            cwd=str(project_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=300  # 5 min max
        )

        output = stdout.decode("utf-8", errors="ignore")

        # Listar archivos creados
        files = []
        for f in project_dir.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                files.append(str(f.relative_to(project_dir)))

        return {
            "success": True,
            "path": str(project_dir),
            "files": files,
            "output": output[:500],
            "message": f"Listo. {len(files)} archivos en {project_dir}",
        }

    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout — la tarea tardó más de 5 minutos"}
    except FileNotFoundError:
        return {"success": False, "error": f"Claude Code no encontrado en {CLAUDE_PATH}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def is_code_task(message: str) -> bool:
    """Detecta si el mensaje es una tarea de código/generación."""
    m = message.lower()
    triggers = [
        "genera", "generame", "crea", "creame", "hazme", "haz",
        "programa", "programame", "codigo", "script",
        "pagina web", "página web", "landing", "website",
        "aplicacion", "aplicación", "app",
        "dashboard", "formulario", "calculadora",
        "html", "css", "javascript", "python", "react",
        "automatiza", "bot", "herramienta",
    ]
    return any(t in m for t in triggers)
