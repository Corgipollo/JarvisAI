"""capcut_pipeline.py - Pipeline GUI E2E genérico (CapCut/Paint/cualquier editor).

Toma un guion YAML, abre la app, importa assets, edita, exporta, verifica el
archivo final en disco. Usa anthropic_computer_use como cerebro + closed_loop
como manos.

YAML schema (cap_test_dummy.yaml):
    app:
        binary: "C:\\Program Files\\CapCut\\CapCut.exe"  # ruta absoluta
        window_title_contains: "CapCut"   # para guardrail
        launch_wait_s: 8
    assets:
        - "C:/.../panel_001.png"
        - "C:/.../narration.mp3"
    output:
        path: "C:/.../cap_31.mp4"
        format: "mp4"
        verify_size_min_bytes: 10000
    instructions:           # natural language para el agent
        - "Importa los assets listados al proyecto"
        - "Arrastra los assets a la timeline"
        - "Exporta como MP4 1080p al path indicado"
    max_iterations: 25
    tenant_id: "default"

API publica:
    run_pipeline(yaml_path) -> dict
        {ok, output_file_exists, output_size_bytes, iterations,
         actions_executed, total_cost_usd, error}

Diseño defensivo:
    - GUARDRAIL: si app.binary no existe -> fail-fast sin tocar nada.
    - GUARDRAIL: foreground window debe contener window_title_contains
      antes de mandar input al modelo (igual que test_notepad_e2e).
    - max_iterations hard cap.
    - Output verify: existe + size > min.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:
        import subprocess as _sp
        _sp.check_call([sys.executable, "-m", "pip", "install", "-q", "pyyaml"])
        import yaml
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _foreground_title() -> str:
    import ctypes
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    length = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _launch_app(binary: str, launch_wait_s: int = 8,
                window_title_contains: str = "") -> dict:
    """Lanza app + espera + force_maximize. GUARDRAIL: confirma foreground."""
    bin_path = Path(binary)
    if not bin_path.exists():
        return {"ok": False, "error": f"binary_not_found:{binary}"}
    try:
        proc = subprocess.Popen([str(bin_path)])
    except Exception as e:
        return {"ok": False, "error": f"launch_fail:{e}"}

    # Esperar window
    time.sleep(launch_wait_s)
    from jarvis_v2.skills.window_control import (
        force_maximize_window, find_window_by_title,
    )
    if window_title_contains:
        hwnd = find_window_by_title(window_title_contains)
        if not hwnd:
            # 2do intento con espera extra
            time.sleep(3)
            hwnd = find_window_by_title(window_title_contains)
        if hwnd:
            force_maximize_window(window_title_contains, retries=3)
        time.sleep(1.5)

    return {"ok": True, "pid": proc.pid}


def _check_output(out_path: str, min_bytes: int = 0) -> dict:
    p = Path(out_path)
    if not p.exists():
        return {"ok": False, "exists": False, "size": 0,
                "error": f"output_file_missing:{out_path}"}
    size = p.stat().st_size
    if size < min_bytes:
        return {"ok": False, "exists": True, "size": size,
                "error": f"size_below_min:{size}<{min_bytes}"}
    return {"ok": True, "exists": True, "size": size}


def run_pipeline(yaml_path: str | Path) -> dict:
    """E2E completo: launch -> agentic loop -> export -> verify disk."""
    from jarvis_v2.core.tenant_context import (
        tenant_session, log_action,
    )
    from jarvis_v2.core.industry_router import route
    from jarvis_v2.skills.anthropic_computer_use import run_agentic

    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        return {"ok": False, "error": f"yaml_not_found:{yaml_path}"}
    cfg = _load_yaml(yaml_path)
    app_cfg = cfg.get("app", {})
    out_cfg = cfg.get("output", {})
    instructions = cfg.get("instructions", [])
    tenant_id = cfg.get("tenant_id", "default")
    max_iter = int(cfg.get("max_iterations", 25))
    model = cfg.get("model", "claude-haiku-4-5-20251001")

    report = {
        "ok": False,
        "yaml": str(yaml_path),
        "app": app_cfg.get("binary"),
        "output_target": out_cfg.get("path"),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "phases": {},
    }

    # FASE 1 - launch
    launch_r = _launch_app(
        binary=app_cfg.get("binary", ""),
        launch_wait_s=int(app_cfg.get("launch_wait_s", 8)),
        window_title_contains=app_cfg.get("window_title_contains", ""),
    )
    report["phases"]["launch"] = launch_r
    if not launch_r.get("ok"):
        report["error"] = launch_r.get("error")
        return report

    # FASE 2 - GUARDRAIL foreground
    fg = _foreground_title()
    needed = app_cfg.get("window_title_contains", "").lower()
    if needed and needed not in fg.lower():
        report["phases"]["guardrail"] = {
            "ok": False, "expected_in_title": needed, "actual": fg,
            "error": "foreground_mismatch_ABORT",
        }
        report["error"] = "guardrail_foreground_mismatch"
        return report
    report["phases"]["guardrail"] = {"ok": True, "foreground": fg}

    # FASE 3 - construir objective para el agent
    objective_parts = [
        f"Estoy en la aplicacion '{fg}'. "
        f"Tu objetivo: {cfg.get('goal', 'completar el pipeline editorial')}.\n",
        "Pasos a ejecutar EN ORDEN:",
    ]
    for i, step in enumerate(instructions, 1):
        objective_parts.append(f"  {i}. {step}")
    objective_parts.append(
        f"\nOutput final esperado: archivo en '{out_cfg.get('path')}'. "
        "Verifica visualmente que cada accion tuvo efecto antes de la "
        "siguiente. Cuando completes el export, responde SIN tool_use con "
        "resumen final."
    )
    objective = "\n".join(objective_parts)

    # FASE 4 - agentic loop
    mask = route(objective, tenant_id=tenant_id)
    with tenant_session(tenant_id, industry=mask["industry"], mask=mask):
        agent_r = run_agentic(
            objective,
            max_iterations=max_iter,
            model=model,
            system_prompt=mask["system_prompt"],
        )
    report["phases"]["agentic"] = agent_r

    # FASE 5 - verify output file in disk
    check = _check_output(
        out_cfg.get("path", ""),
        int(out_cfg.get("verify_size_min_bytes", 0)),
    )
    report["phases"]["output_verify"] = check

    overall_ok = (
        launch_r.get("ok") and agent_r.get("ok") and check.get("ok")
    )
    report["ok"] = bool(overall_ok)
    report["ended_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # Telemetría
    log_action(
        action_type="capcut_pipeline_run",
        target_or_command=str(yaml_path),
        success=int(overall_ok),
        objective_summary=cfg.get("goal", "")[:200],
        elapsed_ms=None,
        error=None if overall_ok else (report.get("error") or "pipeline_fail"),
    )
    return report


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("yaml", help="ruta al YAML del guion")
    args = p.parse_args()
    r = run_pipeline(args.yaml)
    print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
