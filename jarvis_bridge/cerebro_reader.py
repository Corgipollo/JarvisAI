"""cerebro_reader.py — Acceso al cerebro Obsidian de Emmanuel.

Da a Jarvis acceso de LECTURA al vault CerebroEmmanuel:
  - search_notes(query)      buscar notas por contenido (grep)
  - read_note(path)          leer una nota especifica
  - list_projects()          listar proyectos activos
  - read_moc(project)        leer el MOC de un proyecto
  - get_context_for(query)   sintetiza contexto relevante

Cuando Jarvis aprende skills, llama get_context_for() para saber:
  - "este task es sobre GROP" → lee 01-Proyectos/GROP-Ecommerce/
  - "esto involucra trading" → lee 01-Proyectos/Bot-Forex-V8/
  - "esto toca el video Manhwa" → lee 01-Proyectos/Manhua-Narrado/

WRITE access (guardar aprendizajes nuevos al vault) está OFF por seguridad.
Para activar: setear CEREBRO_WRITE_OK=1.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

VAULT = Path(r"C:\Users\Emmanuel\Documents\CerebroEmmanuel")


def search_notes(query: str, max_results: int = 15) -> list[dict]:
    """Grep en todas las notas .md del vault."""
    if not VAULT.exists():
        return []
    results = []
    try:
        # Use ripgrep si disponible, fallback a Python grep
        if subprocess.run(["rg", "--version"], capture_output=True).returncode == 0:
            proc = subprocess.run(
                ["rg", "-l", "-i", query, "--type", "md", str(VAULT)],
                capture_output=True, text=True, timeout=15,
                encoding="utf-8", errors="replace",
            )
            for path in proc.stdout.splitlines()[:max_results]:
                p = Path(path)
                if p.exists():
                    results.append({
                        "path": str(p.relative_to(VAULT)),
                        "name": p.stem,
                        "size_kb": round(p.stat().st_size / 1024, 1),
                    })
            return results
    except Exception:
        pass

    # Fallback Python
    for md_file in VAULT.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            if query.lower() in content.lower():
                results.append({
                    "path": str(md_file.relative_to(VAULT)),
                    "name": md_file.stem,
                    "size_kb": round(md_file.stat().st_size / 1024, 1),
                })
                if len(results) >= max_results:
                    break
        except Exception:
            continue
    return results


def read_note(relative_path: str, max_chars: int = 8000) -> dict:
    """Lee una nota especifica."""
    p = VAULT / relative_path
    if not p.exists():
        return {"error": f"nota no existe: {relative_path}"}
    if not p.is_file():
        return {"error": f"no es archivo: {relative_path}"}
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        return {
            "path": str(p.relative_to(VAULT)),
            "name": p.stem,
            "content": content[:max_chars],
            "truncated": len(content) > max_chars,
            "total_chars": len(content),
        }
    except Exception as e:
        return {"error": str(e)}


def list_projects() -> list[str]:
    """Lista proyectos activos (carpetas en 01-Proyectos)."""
    proyectos = VAULT / "01-Proyectos"
    if not proyectos.exists():
        return []
    return sorted([d.name for d in proyectos.iterdir() if d.is_dir()])


def read_moc(project: str) -> dict | None:
    """Lee el MOC (Map of Content) de un proyecto."""
    proyecto_dir = VAULT / "01-Proyectos" / project
    if not proyecto_dir.exists():
        return None
    # Buscar MOC.md o "MOC - X.md"
    candidates = (list(proyecto_dir.glob("MOC*.md")) +
                  list(proyecto_dir.glob("00 - INDEX*.md")) +
                  list(proyecto_dir.glob("README*.md")))
    if not candidates:
        # Cualquier .md en raíz del proyecto
        candidates = list(proyecto_dir.glob("*.md"))
    if not candidates:
        return None
    moc_file = sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[0]
    return read_note(str(moc_file.relative_to(VAULT)))


def get_context_for(query: str, max_notes: int = 5) -> str:
    """Sintetiza contexto del vault relevante para un query.

    Retorna texto markdown con notas relevantes para inyectar al prompt.
    """
    notes = search_notes(query, max_results=max_notes)
    if not notes:
        return f"(sin contexto relevante en vault para '{query}')"

    ctx_parts = [f"=== CONTEXTO DEL VAULT ({len(notes)} notas relevantes) ==="]
    for n in notes:
        full = read_note(n["path"], max_chars=2000)
        if "content" in full:
            ctx_parts.append(
                f"\n--- {n['path']} ({n['size_kb']} KB) ---\n"
                f"{full['content']}"
            )
    return "\n".join(ctx_parts)


def vault_stats() -> dict:
    """Stats generales del vault."""
    if not VAULT.exists():
        return {"error": "vault no existe"}
    md_files = list(VAULT.rglob("*.md"))
    projects = list_projects()
    return {
        "vault_path": str(VAULT),
        "total_notes": len(md_files),
        "total_size_mb": round(sum(f.stat().st_size for f in md_files) / 1e6, 1),
        "projects_count": len(projects),
        "projects": projects,
    }


def append_to_historial(text: str) -> bool:
    """Append a 04-Diario/historial-preguntas.md (solo si CEREBRO_WRITE_OK=1)."""
    if os.environ.get("CEREBRO_WRITE_OK") != "1":
        return False
    f = VAULT / "04-Diario" / "historial-preguntas.md"
    if not f.exists():
        return False
    with f.open("a", encoding="utf-8") as fp:
        fp.write("\n" + text + "\n")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps(vault_stats(), ensure_ascii=False, indent=2))
        sys.exit(0)
    cmd = sys.argv[1]
    if cmd == "search":
        query = " ".join(sys.argv[2:])
        print(json.dumps(search_notes(query), ensure_ascii=False, indent=2))
    elif cmd == "read":
        path = " ".join(sys.argv[2:])
        print(json.dumps(read_note(path), ensure_ascii=False, indent=2))
    elif cmd == "projects":
        print(json.dumps(list_projects(), ensure_ascii=False, indent=2))
    elif cmd == "moc":
        proj = " ".join(sys.argv[2:])
        print(json.dumps(read_moc(proj), ensure_ascii=False, indent=2))
    elif cmd == "context":
        query = " ".join(sys.argv[2:])
        print(get_context_for(query))
    elif cmd == "stats":
        print(json.dumps(vault_stats(), ensure_ascii=False, indent=2))
    else:
        print(f"Comando desconocido: {cmd}")
        print("Comandos: search/read/projects/moc/context/stats")
