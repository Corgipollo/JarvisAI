"""files.py — File ops para Jarvis: leer, escribir, copiar, listar, search.

Operaciones seguras con limites de tamaño y validacion de paths.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

MAX_READ_BYTES = 10 * 1024 * 1024  # 10 MB


def read_file(path: str, encoding: str = "utf-8") -> dict:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.exists():
        return {"success": False, "error": f"no existe: {p}"}
    if not p.is_file():
        return {"success": False, "error": f"no es archivo: {p}"}
    if p.stat().st_size > MAX_READ_BYTES:
        return {"success": False, "error": f"archivo > {MAX_READ_BYTES} bytes"}
    try:
        return {"success": True, "path": str(p), "content": p.read_text(encoding=encoding)}
    except UnicodeDecodeError:
        return {"success": False, "error": "archivo binario, no se puede leer como texto"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(path: str, content: str, encoding: str = "utf-8", append: bool = False) -> dict:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        mode = "a" if append else "w"
        with p.open(mode, encoding=encoding) as f:
            f.write(content)
        return {"success": True, "path": str(p), "bytes": len(content.encode(encoding))}
    except Exception as e:
        return {"success": False, "error": str(e)}


def copy_file(src: str, dst: str) -> dict:
    s = Path(os.path.expandvars(os.path.expanduser(src)))
    d = Path(os.path.expandvars(os.path.expanduser(dst)))
    if not s.exists():
        return {"success": False, "error": f"src no existe: {s}"}
    try:
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(s, d)
        return {"success": True, "src": str(s), "dst": str(d)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_dir(path: str = ".") -> dict:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.is_dir():
        return {"success": False, "error": f"no es directorio: {p}"}
    try:
        items = []
        for item in sorted(p.iterdir()):
            try:
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": stat.st_size if item.is_file() else 0,
                })
            except Exception:
                continue
        return {"success": True, "path": str(p), "items": items, "count": len(items)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def find_files(root: str, pattern: str, max_results: int = 100) -> dict:
    p = Path(os.path.expandvars(os.path.expanduser(root)))
    if not p.is_dir():
        return {"success": False, "error": f"root no es dir: {p}"}
    try:
        matches = []
        for match in p.rglob(pattern):
            matches.append(str(match))
            if len(matches) >= max_results:
                break
        return {"success": True, "pattern": pattern, "matches": matches, "count": len(matches)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def grep(path: str, pattern: str, ignore_case: bool = True) -> dict:
    """Busca lineas con pattern en un archivo."""
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.is_file():
        return {"success": False, "error": f"no es archivo: {p}"}
    try:
        import re
        flags = re.IGNORECASE if ignore_case else 0
        rx = re.compile(pattern, flags)
        matches = []
        with p.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if rx.search(line):
                    matches.append({"line": i, "text": line.rstrip()})
                    if len(matches) >= 200:
                        break
        return {"success": True, "pattern": pattern, "matches": matches}
    except Exception as e:
        return {"success": False, "error": str(e)}


def file_info(path: str) -> dict:
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    if not p.exists():
        return {"success": False, "error": f"no existe: {p}"}
    try:
        stat = p.stat()
        return {
            "success": True,
            "path": str(p),
            "is_dir": p.is_dir(),
            "is_file": p.is_file(),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / 1e6, 2),
            "modified": stat.st_mtime,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
