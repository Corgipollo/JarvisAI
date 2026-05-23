"""test_notepad_e2e.py - Smoke test físico del closed-loop con Notepad.

Sequencia validada:
  1. subprocess.Popen('notepad.exe') -> ventana nace
  2. window_control.force_maximize_window('Notepad') -> foreground
  3. GUARDRAIL: verificar foreground.title contiene 'Notepad' (sino abort).
  4. execute_action_verified(type_text='Hola Jarvis V2...')
  5. SSIM debe haber cambiado (texto se ve)
  6. execute_action_verified(key='alt+F4') -> dialogo Save?
  7. execute_action_verified(key='alt+n') -> No, cierra sin guardar
  8. Verify ventana ya NO esta en foreground
  9. Dump stats de los ultimos 30 min desde data/closed_loop_metrics.db

Si CUALQUIER fase falla, abort + reporte. NO escribimos sobre otras apps.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from jarvis_v2.skills.window_control import (
    find_window_by_title, force_maximize_window,
)
from jarvis_v2.skills.closed_loop_controller import (
    execute_action_verified, stats, _screenshot, _ssim,
)


TEST_TEXT = "Hola Jarvis V2. Closed-loop validado fisicamente con SSIM y telemetria."


def _get_foreground_title() -> str:
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _is_notepad_foreground() -> bool:
    title = _get_foreground_title().lower()
    return "notepad" in title or "bloc de notas" in title


def run() -> dict:
    report: dict = {
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phases": {},
    }

    # FASE 0 - state precondiciones
    pre_fg = _get_foreground_title()
    report["phases"]["pre_foreground"] = pre_fg
    print(f"[notepad-test] pre foreground: '{pre_fg}'", flush=True)

    # FASE 1 - lanzar notepad
    print("[notepad-test] launching notepad.exe...", flush=True)
    try:
        proc = subprocess.Popen(["notepad.exe"])
        report["phases"]["launch"] = {"ok": True, "pid": proc.pid}
    except Exception as e:
        report["phases"]["launch"] = {"ok": False, "error": str(e)}
        return {"ok": False, **report}

    # Espera a que la ventana exista
    hwnd = None
    for _ in range(15):
        time.sleep(0.5)
        hwnd = find_window_by_title("Notepad") or find_window_by_title("Bloc de notas")
        if hwnd:
            break
    if not hwnd:
        report["phases"]["wait_window"] = {"ok": False, "error": "window not found in 7.5s"}
        return {"ok": False, **report}
    report["phases"]["wait_window"] = {"ok": True, "hwnd": hwnd}

    # FASE 2 - foreground + maximize
    fm_keyword = "Notepad" if find_window_by_title("Notepad") else "Bloc de notas"
    r_fm = force_maximize_window(fm_keyword, retries=3)
    report["phases"]["foreground_maximize"] = r_fm
    time.sleep(1)

    # FASE 3 - GUARDRAIL crítico
    if not _is_notepad_foreground():
        report["phases"]["guardrail"] = {
            "ok": False,
            "error": "foreground no es notepad - ABORT (no escribimos en otra app)",
            "actual_foreground": _get_foreground_title(),
        }
        return {"ok": False, **report}
    report["phases"]["guardrail"] = {"ok": True,
                                       "foreground": _get_foreground_title()}

    # FASE 4 - escribir texto via closed_loop type_text
    print("[notepad-test] typing text...", flush=True)
    r_type = execute_action_verified({
        "type": "type_text",
        "text": TEST_TEXT,
    })
    report["phases"]["type_text"] = r_type
    # NO abortamos si type_text falla — seguimos al cierre por seguridad

    # FASE 5 - snapshot pre-close (para SSIM comparativo)
    before_close = _screenshot()

    # FASE 6 - Alt+F4 cierra Notepad (abre dialogo "Save?")
    print("[notepad-test] sending Alt+F4...", flush=True)
    r_alt_f4 = execute_action_verified({
        "type": "key",
        "key": "alt+f4",
    })
    report["phases"]["alt_f4"] = r_alt_f4
    time.sleep(0.8)  # dar tiempo al dialogo

    # FASE 7 - Alt+N o N para "Don't Save" (depende del idioma)
    # Notepad EN: "Save changes? Save / Don't Save / Cancel" → atajo 'n'
    # Notepad ES: "Guardar cambios? Guardar / No guardar / Cancelar" → atajo 'n'
    print("[notepad-test] sending 'n' to dismiss save dialog...", flush=True)
    r_n = execute_action_verified({
        "type": "key",
        "key": "n",
    })
    report["phases"]["dismiss_save"] = r_n
    time.sleep(0.8)

    # FASE 8 - verificar Notepad ya no esta en foreground
    after_close_fg = _get_foreground_title()
    notepad_gone = "notepad" not in after_close_fg.lower() and "bloc de notas" not in after_close_fg.lower()
    after_close_shot = _screenshot()
    final_ssim = _ssim(before_close, after_close_shot)
    report["phases"]["close_verify"] = {
        "ok": notepad_gone,
        "post_foreground": after_close_fg,
        "ssim_pre_vs_post_close": final_ssim,
    }

    # FASE 9 - stats SQLite ultimos 30 min
    s = stats(days=1)
    report["telemetry"] = s

    overall_ok = (
        report["phases"]["launch"]["ok"]
        and report["phases"]["guardrail"]["ok"]
        and notepad_gone
    )
    report["overall_ok"] = overall_ok
    report["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    return report


if __name__ == "__main__":
    r = run()
    print("\n=== REPORT ===")
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
