"""AUTO_TALK_TO_CLAUDE.py — Abre Claude CLI con SUPER_PROMPT ya enviado.

Flujo:
  1. Lee SUPER_PROMPT_VM.md
  2. Lo manda a Claude CLI con `claude -p` (non-interactive, 1 sola response)
  3. Claude responde con el plan completo (toma decisiones, ejecuta cosas)
  4. Después abre `claude --continue` para que el usuario siga conversando
     en la misma sesión sin tener que copiar el contexto.

Llamado al final de START_JARVIS.bat. Cero intervención humana.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent
SUPER_PROMPT = ROOT / "SUPER_PROMPT_VM.md"


def find_claude() -> str:
    """Busca el ejecutable de Claude CLI."""
    for name in ("claude", "claude.cmd", "claude.exe"):
        path = shutil.which(name)
        if path:
            return path
    # Fallback común en Windows
    candidates = [
        Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",
        Path("C:/Program Files/nodejs/claude.cmd"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return ""


def banner(msg: str):
    line = "=" * 70
    print(f"\n{line}\n  {msg}\n{line}\n", flush=True)


def main():
    if not SUPER_PROMPT.exists():
        print(f"ERROR: no encuentro {SUPER_PROMPT}")
        sys.exit(1)

    claude_bin = find_claude()
    if not claude_bin:
        print("ERROR: claude CLI no instalado. Ejecuta: npm install -g @anthropic-ai/claude-code")
        print("Luego: claude login")
        sys.exit(1)

    prompt = SUPER_PROMPT.read_text(encoding="utf-8")
    banner(f"AUTO-ENVIANDO SUPER PROMPT A CLAUDE ({len(prompt)} chars)")
    print(f"Claude CLI: {claude_bin}")
    print(f"Modelo:     claude-sonnet-4-6")
    print(f"Prompt:     {SUPER_PROMPT.name}")
    print()

    # Verificar login (claude --version y health check)
    try:
        r = subprocess.run(
            [claude_bin, "--version"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(f"ADVERTENCIA: claude --version dio rc={r.returncode}")
            print(f"  stderr: {r.stderr[:200]}")
        else:
            print(f"Version: {r.stdout.strip()}")
    except Exception as e:
        print(f"WARN: no pude verificar version: {e}")

    print()
    banner("ENVIANDO PROMPT (Claude responde aquí abajo)")

    # PASO 1: mandar prompt con -p (modo non-interactive, 1 respuesta)
    try:
        result = subprocess.run(
            [
                claude_bin, "-p", prompt,
                "--dangerously-skip-permissions",
                "--model", "claude-sonnet-4-6",
            ],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            print(f"\n[claude -p] rc={result.returncode}")
            print("Si dice 'Not logged in', ejecuta primero: claude login")
            sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\nCancelado por usuario.")
        sys.exit(130)
    except Exception as e:
        print(f"ERROR ejecutando claude: {e}")
        sys.exit(1)

    print()
    banner("PRIMERA RESPUESTA RECIBIDA. ABRIENDO SESIÓN INTERACTIVA...")
    time.sleep(2)

    # PASO 2: continuar interactivo en la misma sesión
    try:
        subprocess.run(
            [claude_bin, "--continue", "--dangerously-skip-permissions"],
            text=True,
        )
    except KeyboardInterrupt:
        pass

    banner("FIN DE SESIÓN. Servicios siguen corriendo en background.")


if __name__ == "__main__":
    main()
