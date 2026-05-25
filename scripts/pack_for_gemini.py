"""pack_for_gemini.py - Empaqueta TODO el codigo de JarvisAI en 1 .txt.

Genera C:\\Users\\Emmanuel\\Documents\\JarvisAI_full_source.txt con:
  - Todos los .py, .yaml, .yml, .md, .json (config), .bat, .ps1, .toml
  - Cada archivo precedido por header: ===== FILE: relative/path =====
  - Excluye binarios, logs, caches, modelos, DBs, virtualenvs

Listo para subir a Gemini AI Studio (hasta 2M tokens ~= 8 MB texto).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # C:\Users\Emmanuel\Documents\JarvisAI
OUT = Path(r"C:\Users\Emmanuel\Documents\JarvisAI_full_source.txt")

INCLUDE_EXT = {
    ".py", ".yaml", ".yml", ".md", ".bat", ".ps1", ".sh",
    ".toml", ".cfg", ".ini", ".txt", ".json", ".html", ".css", ".js",
    ".tsx", ".jsx", ".ts", ".env", ".example", ".gitignore",
}

EXCLUDE_DIRS = {
    "__pycache__", ".git", ".venv", "venv", "env", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "dist", "build",
    "models", "chroma_cerebro", "api_tasks", "backups", "brave_profile",
    "deep_research_cache", ".cache",
    # Excluir adicionales para reducir tamano para Gemini:
    "claude_global",      # skills externas, no son codigo Jarvis V2
    "video_analysis",     # data dumps
    "tenants",            # DBs por tenant
    "reports",            # outputs generados, no codigo
    "templates_evolved",  # variantes generadas
    "social_cookies",     # secrets sensibles
    "test_results",       # outputs de tests
    "BotForexV8-COMPLETO", "BotForexV8-V3-Backup_20260411-164817",  # otros repos
    "tests",              # opcional: excluir tests si saturan
    "manhwa-narrado", "manhwa_narrado",  # otro proyecto
}

# Excluir archivos especificos (logs, dbs, binarios, output enormes)
EXCLUDE_EXT = {
    ".log", ".err", ".out", ".db", ".sqlite", ".sqlite3", ".db-journal",
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".pdf", ".png", ".jpg",
    ".jpeg", ".gif", ".mp4", ".mp3", ".wav", ".ogg", ".zip", ".tar",
    ".gz", ".rar", ".7z", ".pt", ".pth", ".onnx", ".bin", ".safetensors",
    ".jsonl",  # ledgers/transcripts pueden ser huge
    ".bak", ".tmp",
}

# Archivos especiales: skip individualmente (huge o no relevantes)
EXCLUDE_FILES = {
    "package-lock.json", "yarn.lock", "Pipfile.lock", "poetry.lock",
    "uv.lock", "task_queue.json", "agencia_autonoma_live.md",
}

MAX_FILE_KB = 150  # skip files > 150 KB (suele ser data, no codigo)

# Top-level dirs/files que SI incluimos (whitelist mas estricta)
# Si esta lista no esta vacia, SOLO se incluyen archivos cuyo top-level part este aqui
WHITELIST_TOP = {
    "jarvis_v2", "jarvis_bridge", "scripts", "backend",
    "README.md", ".env", ".env.example", "requirements.txt",
    "pyproject.toml", "setup.py", "setup.cfg",
    "START_JARVIS_FULL.bat", "START_JARVIS_V2.bat", "START_JARVIS.bat",
    "START_HEARTBEAT.bat", "start-jarvis.bat",
}


def should_include(path: Path) -> tuple[bool, str]:
    rel = path.relative_to(ROOT)
    # Whitelist top-level
    if WHITELIST_TOP and rel.parts[0] not in WHITELIST_TOP:
        return False, f"not_in_whitelist:{rel.parts[0]}"
    # Skip si esta en dir excluido
    for part in rel.parts:
        if part in EXCLUDE_DIRS:
            return False, f"in_excluded_dir:{part}"
    # Skip si extension excluida
    if path.suffix.lower() in EXCLUDE_EXT:
        return False, "excluded_ext"
    # Skip si filename excluido
    if path.name in EXCLUDE_FILES:
        return False, "excluded_filename"
    # Skip si sin extension incluida (a menos que sea archivo especial)
    if path.suffix.lower() not in INCLUDE_EXT and path.name not in {".env", "Dockerfile", "Makefile", ".gitignore"}:
        return False, "not_included_ext"
    # Skip si > MAX_FILE_KB
    try:
        if path.stat().st_size > MAX_FILE_KB * 1024:
            return False, f"too_big_{path.stat().st_size//1024}KB"
    except Exception:
        return False, "stat_err"
    return True, "ok"


def main():
    files_included = []
    files_skipped: dict[str, int] = {}
    total_chars = 0

    with OUT.open("w", encoding="utf-8") as out:
        out.write("=" * 80 + "\n")
        out.write("JARVIS V2 - FULL SOURCE CODE EXPORT FOR GEMINI\n")
        out.write(f"Source root: {ROOT}\n")
        out.write(f"Generated: {__import__('datetime').datetime.now().isoformat()}\n")
        out.write("=" * 80 + "\n\n")

        # Recorrer en orden alfabetico para output reproducible
        all_paths = sorted(ROOT.rglob("*"))
        for path in all_paths:
            if not path.is_file():
                continue
            include, reason = should_include(path)
            if not include:
                files_skipped[reason] = files_skipped.get(reason, 0) + 1
                continue
            rel = path.relative_to(ROOT)
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                files_skipped[f"read_err:{e.__class__.__name__}"] = (
                    files_skipped.get(f"read_err:{e.__class__.__name__}", 0) + 1
                )
                continue
            header = f"\n{'=' * 80}\n===== FILE: {rel.as_posix()} ({len(content)} chars)\n{'=' * 80}\n"
            out.write(header)
            out.write(content)
            if not content.endswith("\n"):
                out.write("\n")
            files_included.append((str(rel), len(content)))
            total_chars += len(content)

        # Footer con stats
        out.write("\n" + "=" * 80 + "\n")
        out.write(f"END EXPORT - {len(files_included)} files, {total_chars} total chars\n")
        out.write("=" * 80 + "\n")

    size_mb = OUT.stat().st_size / (1024 * 1024)
    print(f"Output: {OUT}")
    print(f"Size: {size_mb:.2f} MB ({total_chars:,} chars)")
    print(f"Files included: {len(files_included)}")
    print(f"\nTop 10 largest files included:")
    for rel, sz in sorted(files_included, key=lambda x: -x[1])[:10]:
        print(f"  {sz//1024:>4} KB  {rel}")
    print(f"\nSkipped by reason (top 10):")
    for reason, n in sorted(files_skipped.items(), key=lambda x: -x[1])[:10]:
        print(f"  {n:>5}  {reason}")


if __name__ == "__main__":
    main()
