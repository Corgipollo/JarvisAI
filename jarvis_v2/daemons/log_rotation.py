"""log_rotation.py - Rotacion automatica de logs Jarvis V2.

Problema: data/*.log crecen sin control. proxy_fast.log, infinite_ceo.log,
api.log pueden llegar a >500MB en semanas. SSD se llena, IO baja, indexer
de Windows tambien se vuelve loco.

Solucion: cada hora, escanea data/*.log y JarvisAI/*.log:
  - Si tamano > MAX_LOG_MB (default 50MB):
      1. mueve a {name}.{YYYYMMDD-HHMM}.log
      2. gzip lo movido
      3. trunca el original a 0 bytes (cat > / Set-Content)
      4. mantiene N archivos comprimidos por log (cap default 5)
      5. los archivos viejos los borra
  - Total disco usado por rotacion: capped a N * MAX_LOG_MB / 10 (gzip ~10x).

Registrado como schtask Jarvis_LogRotation cada 60 min.
Append-only friendly: no afecta procesos escribiendo via tee/append; ellos
seguiran abriendo el archivo truncado y agregando desde 0.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Forzar UTF-8 en stdout (Windows cp1252 rompe con simbolos unicode)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

MAX_LOG_MB = int(os.environ.get("JARVIS_MAX_LOG_MB", "50"))
KEEP_ROTATED = int(os.environ.get("JARVIS_KEEP_ROTATED", "5"))
LOG_GLOBS = [
    DATA_DIR.glob("*.log"),
    ROOT.glob("*.log"),
]

# Patron para identificar rotados nuestros: name.YYYYMMDD-HHMM.log.gz
ROTATED_PATTERN = re.compile(r"^(?P<name>.+)\.(?P<ts>\d{8}-\d{4})\.log\.gz$")


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except FileNotFoundError:
        return 0.0


def _rotate_one(log_path: Path) -> dict:
    size_mb = _size_mb(log_path)
    if size_mb < MAX_LOG_MB:
        return {"file": str(log_path), "skipped": True, "size_mb": round(size_mb, 1)}

    ts = datetime.utcnow().strftime("%Y%m%d-%H%M")
    rotated_path = log_path.with_name(f"{log_path.stem}.{ts}.log")
    gz_path = rotated_path.with_suffix(rotated_path.suffix + ".gz")

    # 1. Copia + gzip (en lugar de move + truncate; mas seguro si el proceso tiene file handle vivo)
    try:
        with log_path.open("rb") as src, gzip.open(gz_path, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst, length=64 * 1024)
    except Exception as e:
        _log(f"copy+gzip failed for {log_path.name}: {e}")
        return {"file": str(log_path), "error": str(e)}

    # 2. Truncar archivo original. Si el proceso tiene handle abierto en modo
    # append, la siguiente escritura va al offset 0. Open con mode "w" no
    # cierra el otro handle pero si trunca via OS.
    try:
        with log_path.open("w", encoding="utf-8", errors="replace") as f:
            f.truncate()
    except Exception as e:
        _log(f"truncate failed for {log_path.name}: {e} (gzip OK however)")

    # 3. Cleanup viejos: mantener KEEP_ROTATED mas recientes de este log
    family_prefix = log_path.stem + "."
    siblings = sorted(
        [p for p in log_path.parent.glob(f"{family_prefix}*.log.gz")
         if ROTATED_PATTERN.match(p.name)],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    deleted = 0
    for old in siblings[KEEP_ROTATED:]:
        try:
            old.unlink()
            deleted += 1
        except Exception as e:
            _log(f"could not delete {old.name}: {e}")

    return {
        "file": str(log_path),
        "rotated_to": str(gz_path),
        "rotated_size_mb": round(size_mb, 1),
        "gz_size_mb": round(_size_mb(gz_path), 2),
        "purged_old": deleted,
    }


def cycle_once() -> dict:
    _log("=== Log rotation cycle start ===")
    candidates: set[Path] = set()
    for glob in LOG_GLOBS:
        for p in glob:
            # Skip rotated archives + gz files
            if p.name.endswith(".gz") or ROTATED_PATTERN.match(p.name):
                continue
            candidates.add(p)

    results = []
    rotated = 0
    for p in sorted(candidates):
        r = _rotate_one(p)
        results.append(r)
        if r.get("rotated_to"):
            rotated += 1
            _log(f"rotated {p.name} ({r['rotated_size_mb']}MB -> {r['gz_size_mb']}MB gz, purged {r['purged_old']})")

    _log(f"=== Cycle end. Rotated {rotated}/{len(candidates)} ===")
    return {"ok": True, "rotated": rotated, "scanned": len(candidates), "details": results}


if __name__ == "__main__":
    if "--loop" in sys.argv:
        while True:
            try:
                cycle_once()
            except Exception as e:
                _log(f"cycle EXCEPTION: {e}")
            time.sleep(3600)
    else:
        r = cycle_once()
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
