"""closed_loop_controller.py - Manos con propiocepcion (Sprint 2).

Ejecuta acciones GUI con verificacion en 5 fases:

    1. parse() screenshot -> grafo semantico
    2. match() target_desc -> coords
    3. move + verify cursor real con pyautogui.position()
    4. snapshot before -> action -> snapshot after
    5. SSIM(before, after) < threshold -> success (la pantalla CAMBIO)
       SSIM >= threshold -> retry o report fail

Log cada accion a data/closed_loop_metrics.db para aprendizaje.

API publica:
    execute_action_verified(action: dict) -> dict
        action = {
            "type": "click" | "double_click" | "right_click" | "drag" |
                    "type_text" | "key",
            "target_desc": "...",        # para click/drag (semantic)
            "dest_desc": "...",          # solo para drag
            "text": "...",               # solo para type_text
            "key": "ctrl+s",             # solo para key
            "max_retries": int,
            "ssim_change_threshold": float (default 0.995),
        }

Diseno: fail-loud, telemetria a SQLite, jamas asume exito.
"""
from __future__ import annotations

import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

METRICS_DB = ROOT / "data" / "closed_loop_metrics.db"
LOG = ROOT / "data" / "closed_loop_controller.log"


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _init_db() -> sqlite3.Connection:
    METRICS_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(METRICS_DB), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS action_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, action_type TEXT, target_desc TEXT,
            target_x INTEGER, target_y INTEGER,
            cursor_landed_x INTEGER, cursor_landed_y INTEGER,
            drift_px INTEGER,
            elements_found INTEGER,
            match_score REAL,
            ssim_before_after REAL,
            success INTEGER,
            elapsed_ms INTEGER,
            error TEXT
        )
    """)
    conn.commit()
    return conn


def _record(conn: sqlite3.Connection, payload: dict) -> None:
    cols = ("ts", "action_type", "target_desc", "target_x", "target_y",
            "cursor_landed_x", "cursor_landed_y", "drift_px",
            "elements_found", "match_score", "ssim_before_after",
            "success", "elapsed_ms", "error")
    values = tuple(payload.get(k) for k in cols)
    conn.execute(
        f"INSERT INTO action_log ({','.join(cols)}) "
        f"VALUES ({','.join(['?'] * len(cols))})",
        values,
    )
    conn.commit()


def _screenshot():
    """Captura primary monitor con mss. Devuelve PIL.Image RGB."""
    import mss
    from PIL import Image
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def _ssim(img_a, img_b) -> float:
    """Structural Similarity entre 2 PIL.Image. 1.0 = identico, <0.9 = cambio claro."""
    import numpy as np
    from skimage.metrics import structural_similarity
    a = np.array(img_a.convert("L"))
    b = np.array(img_b.convert("L"))
    # Resize si difieren (multi-monitor reconfig)
    if a.shape != b.shape:
        from PIL import Image
        b_pil = Image.fromarray(b).resize((a.shape[1], a.shape[0]))
        b = np.array(b_pil)
    return float(structural_similarity(a, b))


def _cursor_position() -> tuple[int, int]:
    """Posicion actual del cursor. pyautogui.position() es source of truth
    en Windows nativo. Si en futuro detectamos drift (multi-monitor con DPI
    diferente), se puede agregar template match."""
    import pyautogui
    pos = pyautogui.position()
    return (int(pos.x), int(pos.y))


def _move_to(x: int, y: int, duration: float = 0.25) -> tuple[int, int]:
    """Move + retry hasta que cursor llegue cerca (±10px)."""
    import pyautogui
    for attempt in range(3):
        pyautogui.moveTo(x, y, duration=duration)
        time.sleep(0.1)
        cx, cy = _cursor_position()
        if abs(cx - x) <= 10 and abs(cy - y) <= 10:
            return (cx, cy)
        # Corrige overshoot
        pyautogui.moveTo(x + (x - cx), y + (y - cy), duration=0.12)
        time.sleep(0.08)
    return _cursor_position()


def execute_action_verified(action: dict) -> dict:
    """Ejecuta accion con verify 5-fase. Devuelve dict con resultado completo.

    Action types soportados:
      - click | double_click | right_click: requiere target_desc
      - drag: requiere target_desc + dest_desc
      - type_text: requiere text
      - key: requiere key (ej. "ctrl+s")
    """
    start = time.time()
    a_type = action.get("type", "click")
    target_desc = action.get("target_desc", "")
    max_retries = int(action.get("max_retries", 1))
    # Threshold ajustado tras E2E Notepad test 2026-05-23:
    #   - text_input/key cambian regiones pequenas -> SSIM 0.995 era falso-neg
    #   - default ahora 0.985 (cambios sutiles cuentan)
    #   - click sigue siendo mas estricto (0.992) porque debe abrir
    #     menu/dialog/etc.
    default_ssim = 0.985 if a_type in ("type_text", "key") else 0.992
    ssim_threshold = float(action.get("ssim_change_threshold", default_ssim))
    record = {
        "ts": datetime.utcnow().isoformat(),
        "action_type": a_type,
        "target_desc": target_desc,
        "success": 0, "elements_found": 0,
    }
    conn = _init_db()

    try:
        # FASE 1 - Localizar target (si aplica)
        target_x = target_y = None
        match_score = None
        if a_type in ("click", "double_click", "right_click", "drag"):
            from jarvis_v2.skills.omniparser_engine import (
                parse, match,
            )
            shot = _screenshot()
            elements = parse(shot, run_caption=True, max_elements=100)
            record["elements_found"] = len(elements)
            hits = match(elements, target_desc, top_k=1, min_score=0.3)
            if not hits:
                record["error"] = "target_not_found"
                record["elapsed_ms"] = int((time.time() - start) * 1000)
                _record(conn, record)
                return {"ok": False, **record}
            target_x, target_y = hits[0]["center"]
            match_score = hits[0].get("match_score")
            record["target_x"] = target_x
            record["target_y"] = target_y
            record["match_score"] = match_score
            _log(f"target found: ({target_x},{target_y}) score={match_score:.2f}")

        # FASE 2 - Mover cursor + verify (solo si tipo aplica)
        if a_type in ("click", "double_click", "right_click", "drag"):
            cx, cy = _move_to(target_x, target_y)
            drift = max(abs(cx - target_x), abs(cy - target_y))
            record["cursor_landed_x"] = cx
            record["cursor_landed_y"] = cy
            record["drift_px"] = drift
            if drift > 20:
                _log(f"WARN drift {drift}px from target")

        # FASE 3 - Snapshot BEFORE
        before = _screenshot()

        # FASE 4 - Ejecutar accion
        import pyautogui
        if a_type == "click":
            pyautogui.click()
        elif a_type == "double_click":
            pyautogui.doubleClick()
        elif a_type == "right_click":
            pyautogui.rightClick()
        elif a_type == "drag":
            # destino
            dest_desc = action.get("dest_desc", "")
            from jarvis_v2.skills.omniparser_engine import parse, match
            dest_shot = _screenshot()
            dest_elements = parse(dest_shot, run_caption=True)
            dest_hits = match(dest_elements, dest_desc, top_k=1, min_score=0.3)
            if not dest_hits:
                record["error"] = "drag_dest_not_found"
                record["elapsed_ms"] = int((time.time() - start) * 1000)
                _record(conn, record)
                return {"ok": False, **record}
            dx, dy = dest_hits[0]["center"]
            pyautogui.dragTo(dx, dy, duration=0.5, button="left")
        elif a_type == "type_text":
            text = action.get("text", "")
            pyautogui.write(text, interval=0.02)
        elif a_type == "key":
            keys = action.get("key", "").split("+")
            pyautogui.hotkey(*keys)
        else:
            record["error"] = f"unknown_action_type:{a_type}"
            _record(conn, record)
            return {"ok": False, **record}

        # FASE 5 - Snapshot AFTER + SSIM
        time.sleep(0.3)
        after = _screenshot()
        ssim = _ssim(before, after)
        record["ssim_before_after"] = ssim
        changed = ssim < ssim_threshold

        if changed:
            record["success"] = 1
            _log(f"OK {a_type} '{target_desc[:40]}' ssim={ssim:.3f}")
        else:
            record["error"] = f"no_visual_change_ssim={ssim:.4f}"
            _log(f"FAIL {a_type} '{target_desc[:40]}' no visual change ssim={ssim:.4f}")

        record["elapsed_ms"] = int((time.time() - start) * 1000)
        _record(conn, record)
        return {"ok": bool(record["success"]), **record}

    except Exception as e:
        record["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        record["elapsed_ms"] = int((time.time() - start) * 1000)
        _record(conn, record)
        _log(f"EXC in execute_action: {record['error']}")
        return {"ok": False, **record}
    finally:
        conn.close()


def stats(days: int = 7) -> dict:
    """Devuelve metricas de las ultimas N dias para analisis."""
    conn = _init_db()
    cutoff = (datetime.utcnow().timestamp() - days * 86400)
    cutoff_iso = datetime.utcfromtimestamp(cutoff).isoformat()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*), SUM(success), AVG(drift_px), AVG(elapsed_ms), "
        "AVG(ssim_before_after) FROM action_log WHERE ts > ?",
        (cutoff_iso,),
    )
    total, ok, avg_drift, avg_ms, avg_ssim = cur.fetchone()
    cur.execute(
        "SELECT action_type, COUNT(*), SUM(success) FROM action_log "
        "WHERE ts > ? GROUP BY action_type ORDER BY COUNT(*) DESC",
        (cutoff_iso,),
    )
    by_type = [{"type": r[0], "n": r[1], "success": r[2]} for r in cur.fetchall()]
    conn.close()
    return {
        "days": days, "total": total or 0,
        "success_rate": (ok or 0) / total if total else 0.0,
        "avg_drift_px": avg_drift, "avg_elapsed_ms": avg_ms,
        "avg_ssim": avg_ssim, "by_type": by_type,
    }


if __name__ == "__main__":
    import json
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stats", action="store_true",
                        help="Solo imprimir metricas, no ejecutar accion.")
    parser.add_argument("--smoke", action="store_true",
                        help="Smoke test no-destructivo: move cursor + verify SSIM, sin click.")
    parser.add_argument("--type", default="click")
    parser.add_argument("--target", default="")
    args = parser.parse_args()

    if args.stats:
        print(json.dumps(stats(), ensure_ascii=False, indent=2, default=str))
    elif args.smoke:
        # Test seguro: solo mueve a esquina superior izquierda, verify SSIM
        # (NO hace click). Valida que el loop sin fase IV funciona.
        import pyautogui
        start = time.time()
        before = _screenshot()
        sx, sy = pyautogui.size()
        target_x, target_y = sx // 4, sy // 4
        _log(f"smoke: moving cursor to ({target_x},{target_y}) - no click")
        cx, cy = _move_to(target_x, target_y)
        time.sleep(0.3)
        after = _screenshot()
        ssim = _ssim(before, after)
        elapsed = int((time.time() - start) * 1000)
        result = {"ok": True, "smoke": True,
                  "cursor_landed": (cx, cy), "target": (target_x, target_y),
                  "drift_px": max(abs(cx - target_x), abs(cy - target_y)),
                  "ssim_before_after": ssim, "elapsed_ms": elapsed}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        action = {"type": args.type, "target_desc": args.target}
        r = execute_action_verified(action)
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
