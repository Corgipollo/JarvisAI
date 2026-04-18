"""Ejecutor de codigo seguro."""
import subprocess
import sys
import tempfile
import os
from typing import Optional


async def run_python(code: str, timeout: int = 30) -> dict:
    """Ejecuta codigo Python en un subproceso."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout: el codigo tardo mas de {timeout}s", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}
    finally:
        os.unlink(temp_path)


async def run_command(command: str, timeout: int = 15) -> dict:
    """Ejecuta un comando de shell."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Timeout: el comando tardo mas de {timeout}s", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}
