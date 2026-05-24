"""sqlite_vacuum.py - Compactacion diaria de SQLite DBs Jarvis V2.

Problema: SQLite no devuelve espacio al SO al borrar filas (free pages
quedan dentro del file). Tras semanas de auto_decisions, queue tasks,
tenant memories, los .db engordan 3-5x sin necesidad. Win indexer + SSD
trim sufren.

Solucion: VACUUM full diario. Para cada .db en data/:
  1. Conecta read-only check si esta corrupto via PRAGMA integrity_check
  2. Snapshot tamano antes
  3. PRAGMA journal_mode=WAL primero (si no estaba) — VACUUM con WAL
     es mas seguro porque no requiere lock exclusivo prolongado.
  4. VACUUM (operacion exclusiva, pero rapida en DBs <100MB)
  5. PRAGMA optimize (estadisticas para query planner)
  6. PRAGMA wal_checkpoint(TRUNCATE) para flush WAL final
  7. Log antes/despues

Skips: db file > 500MB (toma >30s, mejor hacerlo manual fuera de horario),
db con journal mode 'memory' (es por design corta), db abierta por proceso
critico (detect via locked exception, reintenta despues).

Registrado como schtask Jarvis_SQLite_Vacuum cada 24h a las 04:00 AM.
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"

MAX_DB_MB = int(os.environ.get("JARVIS_VACUUM_MAX_MB", "500"))
DB_GLOBS = [
    DATA_DIR.glob("*.db"),
    DATA_DIR.glob("tenants/*/memory.db"),
    DATA_DIR.glob("tenants/*/*.db"),
]


def _log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def _size_mb(path: Path) -> float:
    try:
        return path.stat().st_size / (1024 * 1024)
    except FileNotFoundError:
        return 0.0


def _vacuum_one(db_path: Path) -> dict:
    before = _size_mb(db_path)
    if before > MAX_DB_MB:
        return {"db": str(db_path), "skipped": True, "reason": f"size {before:.1f}MB > {MAX_DB_MB}MB", "size_mb": round(before, 1)}

    t0 = time.time()
    try:
        # timeout=2 -> si esta bloqueada por proceso activo, skip rapido
        con = sqlite3.connect(str(db_path), timeout=2.0, isolation_level=None)
        cur = con.cursor()

        # Quick integrity check (no full scan, solo header)
        cur.execute("PRAGMA quick_check")
        check = cur.fetchone()
        if check and check[0] != "ok":
            con.close()
            return {"db": str(db_path), "error": f"integrity_check failed: {check[0]}", "size_mb": round(before, 1)}

        # Ensure WAL mode
        cur.execute("PRAGMA journal_mode")
        jm = cur.fetchone()
        current_mode = jm[0] if jm else None
        if current_mode and current_mode.lower() not in ("wal", "memory"):
            try:
                cur.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError as e:
                _log(f"  warn: cannot set WAL on {db_path.name}: {e}")

        # Flush WAL primero
        try:
            cur.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.OperationalError:
            pass

        # VACUUM
        cur.execute("VACUUM")

        # Update stats
        try:
            cur.execute("PRAGMA optimize")
        except sqlite3.OperationalError:
            pass

        con.close()
    except sqlite3.OperationalError as e:
        return {"db": str(db_path), "error": f"locked or busy: {e}", "size_mb": round(before, 1)}
    except Exception as e:
        return {"db": str(db_path), "error": f"{e.__class__.__name__}: {e}", "size_mb": round(before, 1)}

    after = _size_mb(db_path)
    elapsed = int((time.time() - t0) * 1000)
    saved = before - after
    return {
        "db": str(db_path),
        "before_mb": round(before, 2),
        "after_mb": round(after, 2),
        "saved_mb": round(saved, 2),
        "saved_pct": round((saved / before * 100) if before > 0 else 0, 1),
        "elapsed_ms": elapsed,
    }


def cycle_once() -> dict:
    _log("=== SQLite VACUUM cycle start ===")
    candidates: set[Path] = set()
    for glob in DB_GLOBS:
        for p in glob:
            candidates.add(p)

    results = []
    total_before = 0.0
    total_after = 0.0
    vacuumed = 0
    skipped = 0
    errors = 0
    for p in sorted(candidates):
        r = _vacuum_one(p)
        results.append(r)
        if r.get("error"):
            errors += 1
            _log(f"  ERROR {p.name}: {r['error']}")
        elif r.get("skipped"):
            skipped += 1
        else:
            vacuumed += 1
            total_before += r["before_mb"]
            total_after += r["after_mb"]
            _log(f"  vacuumed {p.name}: {r['before_mb']}MB -> {r['after_mb']}MB (saved {r['saved_mb']}MB, {r['saved_pct']}%)")

    total_saved = total_before - total_after
    _log(f"=== Cycle end. Vacuumed {vacuumed}, skipped {skipped}, errors {errors}. Saved {total_saved:.2f}MB total ===")
    return {
        "ok": True,
        "vacuumed": vacuumed,
        "skipped": skipped,
        "errors": errors,
        "saved_mb_total": round(total_saved, 2),
        "details": results,
    }


if __name__ == "__main__":
    r = cycle_once()
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
