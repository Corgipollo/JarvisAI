"""anthropic_computer_use.py - Bridge Anthropic Computer Use API <-> closed_loop.

Conecta el cerebro (Claude Sonnet 4.6 / Haiku 4.5 via OAuth Max proxy $0)
con las manos (jarvis_v2.skills.closed_loop_controller.execute_action_verified).

ESCUDO FINANCIERO (critico):
  - SIEMPRE va al proxy local OAuth (http://127.0.0.1:8088).
  - JAMAS toca api.anthropic.com con API key paga. El daemon proxy_fast
    refresca el token OAuth Max automaticamente, costo marginal = $0.
  - Circuit breaker: MAX_ITERATIONS hard cap. Si el agente entra en bucle,
    aborta a las N iteraciones (default 15).
  - max_tokens_per_call hard cap (default 2048) - evita respuestas inmensas.
  - Per-tenant spend tracking via tenant_context.log_spend().

TOOL TRANSLATION (Anthropic computer_use tool -> closed_loop):

  Anthropic emite:                    Bridge ejecuta:
  ─────────────────                  ─────────────────
  {action: screenshot}              -> mss.grab + return base64
  {action: left_click,              -> execute_action_verified(
   coordinate:[x,y]}                     type='click',
                                          target_xy=(x,y))  # bypass match
  {action: right_click, ...}        -> execute_action_verified(type='right_click', ...)
  {action: double_click, ...}       -> execute_action_verified(type='double_click', ...)
  {action: type, text:"..."}        -> execute_action_verified(type='type_text', text=...)
  {action: key, text:"ctrl+s"}      -> execute_action_verified(type='key', key=...)
  {action: left_click_drag,         -> execute_action_verified(type='drag',
   start_coordinate:[x1,y1],            target_xy=(x1,y1), dest_xy=(x2,y2))
   coordinate:[x2,y2]}
  {action: mouse_move,              -> pyautogui.moveTo solamente (no click)
   coordinate:[x,y]}
  {action: cursor_position}         -> pyautogui.position() inline
  {action: scroll, coordinate,      -> pyautogui.scroll
   scroll_direction, amount}

API:
  run_agentic(objective, screen_size=None, max_iterations=15,
               model='claude-haiku-4-5-20251001') -> dict

Modelos soportados (header beta):
  - 'claude-sonnet-4-6'   + 'computer-use-2025-11-24'
  - 'claude-haiku-4-5-20251001' + 'computer-use-2025-01-24' (default, mas barato)
  - 'claude-opus-4-7'     + 'computer-use-2025-11-24'

NOTA: claude-3-5-sonnet-20241022 deprecado. Default es Haiku 4.5 por
costo + latencia + Computer Use beta vigente.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# ESCUDO FINANCIERO - proxy local OAuth obligatorio
PROXY_URL = os.environ.get("CLAUDE_PROXY_URL", "http://127.0.0.1:8088")
MAX_ITERATIONS_DEFAULT = 15
MAX_TOKENS_DEFAULT = 2048

MODEL_BETAS = {
    "claude-opus-4-7": "computer-use-2025-11-24",
    "claude-opus-4-6": "computer-use-2025-11-24",
    "claude-sonnet-4-6": "computer-use-2025-11-24",
    "claude-opus-4-5": "computer-use-2025-11-24",
    "claude-sonnet-4-5": "computer-use-2025-01-24",
    "claude-haiku-4-5-20251001": "computer-use-2025-01-24",
    "claude-opus-4-1": "computer-use-2025-01-24",
}


def _screen_size() -> tuple[int, int]:
    import pyautogui
    s = pyautogui.size()
    return int(s.width), int(s.height)


def _screenshot_b64() -> str:
    """PNG base64 del screen actual (mss, no pyautogui = mas rapido)."""
    import mss
    from PIL import Image
    with mss.mss() as sct:
        raw = sct.grab(sct.monitors[1])
        img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("ascii")


def _build_computer_tool(width: int, height: int) -> dict:
    """Tool schema Anthropic computer_use (beta)."""
    return {
        "type": "computer_20250124",  # tool version pareada al beta header
        "name": "computer",
        "display_width_px": width,
        "display_height_px": height,
        "display_number": 1,
    }


def _execute_tool_call(tool_input: dict) -> dict:
    """Traduce Anthropic computer_use tool_input -> ejecucion local.

    Devuelve dict con result + opcional screenshot base64.
    """
    action = tool_input.get("action", "")
    if action == "screenshot":
        return {"ok": True, "screenshot_b64": _screenshot_b64()}

    # Para click/drag bypassamos el semantic match: Claude ya escogio coords.
    from jarvis_v2.skills.closed_loop_controller import (
        execute_action_verified, _move_to, _screenshot, _ssim,
    )
    import pyautogui

    if action == "mouse_move":
        coord = tool_input.get("coordinate", [0, 0])
        _move_to(int(coord[0]), int(coord[1]))
        return {"ok": True, "screenshot_b64": _screenshot_b64()}

    if action == "cursor_position":
        p = pyautogui.position()
        return {"ok": True, "position": [int(p.x), int(p.y)]}

    if action in ("left_click", "right_click", "double_click",
                   "middle_click", "triple_click"):
        coord = tool_input.get("coordinate", [0, 0])
        # Move + click sin semantic (Claude ya escogio coord)
        x, y = int(coord[0]), int(coord[1])
        before = _screenshot()
        _move_to(x, y)
        if action == "left_click":
            pyautogui.click()
        elif action == "right_click":
            pyautogui.rightClick()
        elif action == "double_click":
            pyautogui.doubleClick()
        elif action == "middle_click":
            pyautogui.middleClick()
        elif action == "triple_click":
            pyautogui.tripleClick()
        time.sleep(0.3)
        after = _screenshot()
        ssim_v = _ssim(before, after)
        return {"ok": True, "ssim_change": ssim_v,
                "screenshot_b64": _screenshot_b64()}

    if action == "left_click_drag":
        start = tool_input.get("start_coordinate", [0, 0])
        end = tool_input.get("coordinate", [0, 0])
        before = _screenshot()
        _move_to(int(start[0]), int(start[1]))
        pyautogui.dragTo(int(end[0]), int(end[1]), duration=0.5,
                          button="left")
        time.sleep(0.3)
        after = _screenshot()
        ssim_v = _ssim(before, after)
        return {"ok": True, "ssim_change": ssim_v,
                "screenshot_b64": _screenshot_b64()}

    if action == "type":
        text = tool_input.get("text", "")
        r = execute_action_verified({"type": "type_text", "text": text})
        return {"ok": r.get("ok", False), "ssim_change": r.get("ssim_before_after"),
                "screenshot_b64": _screenshot_b64()}

    if action == "key":
        keys = tool_input.get("text", "")
        r = execute_action_verified({"type": "key", "key": keys})
        return {"ok": r.get("ok", False), "ssim_change": r.get("ssim_before_after"),
                "screenshot_b64": _screenshot_b64()}

    if action == "scroll":
        coord = tool_input.get("coordinate")
        direction = tool_input.get("scroll_direction", "down")
        amount = int(tool_input.get("scroll_amount", 3))
        if coord:
            _move_to(int(coord[0]), int(coord[1]))
        delta = amount if direction in ("up", "right") else -amount
        pyautogui.scroll(delta)
        time.sleep(0.3)
        return {"ok": True, "screenshot_b64": _screenshot_b64()}

    if action == "wait":
        duration = float(tool_input.get("duration", 1.0))
        time.sleep(min(duration, 10.0))  # cap 10s para evitar bucles
        return {"ok": True}

    return {"ok": False, "error": f"unknown_action:{action}"}


def run_agentic(objective: str,
                screen_size: tuple[int, int] | None = None,
                max_iterations: int = MAX_ITERATIONS_DEFAULT,
                model: str = "claude-haiku-4-5-20251001",
                system_prompt: str | None = None,
                max_tokens: int = MAX_TOKENS_DEFAULT) -> dict:
    """Loop agentico Claude <-> manos locales.

    Args:
      objective: lo que el usuario quiere lograr ("exporta cap_31 en CapCut").
      screen_size: (W,H) o auto-detect.
      max_iterations: hard cap. Default 15. Aborta el bucle si se excede.
      model: claude-haiku-4-5 default. sonnet-4-6 si tarea compleja.
      system_prompt: opcional, override por industria/tenant.
      max_tokens: por respuesta del modelo, default 2048.

    Returns:
      {"ok": bool, "iterations": int, "final_message": str,
       "actions_executed": int, "total_cost_usd": float (always 0 via OAuth)}
    """
    from jarvis_v2.core.tenant_context import (
        get_tenant, get_industry, log_action, log_spend,
    )

    w, h = screen_size or _screen_size()
    beta_header = MODEL_BETAS.get(model, "computer-use-2025-01-24")
    tools = [_build_computer_tool(w, h)]
    industry = get_industry() or "generic"
    tenant_id = get_tenant()

    sys_prompt = system_prompt or (
        f"Eres Jarvis V2 controlando un equipo Windows 11 ({w}x{h}). "
        f"Vertical: {industry}. Tenant: {tenant_id}. "
        f"Objetivo del usuario: {objective}\n\n"
        "REGLAS:\n"
        "1. Antes de cada accion, screenshot para ver el estado actual.\n"
        "2. Verifica que la accion previa tuvo efecto antes de la siguiente.\n"
        "3. Si una accion no produce cambio en 2 intentos, reporta y aborta.\n"
        f"4. Maximo {max_iterations} acciones. Si excedes, te detendre.\n"
        "5. Cuando completes el objetivo, responde SIN tool_use con resumen final."
    )

    messages: list[dict] = [{
        "role": "user",
        "content": [{"type": "text", "text": objective}],
    }]
    initial_screenshot = _screenshot_b64()
    messages[0]["content"].append({
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png",
                    "data": initial_screenshot},
    })

    actions_executed = 0
    final_message = ""
    iteration = 0
    start = time.time()

    for iteration in range(1, max_iterations + 1):
        # CALL al proxy local (ESCUDO: jamas direct a api.anthropic.com)
        body = {
            "model": model, "max_tokens": max_tokens,
            "system": sys_prompt, "tools": tools, "messages": messages,
            "betas": [beta_header],
        }
        try:
            with httpx.Client(timeout=90) as cli:
                r = cli.post(f"{PROXY_URL}/v1/messages", json=body,
                              headers={"anthropic-beta": beta_header})
        except Exception as e:
            log_action("computer_use_api_call", success=0,
                       error=f"http_exc: {e}", initiated_by="agent")
            return {"ok": False, "error": f"proxy_unreachable: {e}",
                    "iterations": iteration, "actions_executed": actions_executed}

        if r.status_code != 200:
            log_action("computer_use_api_call", success=0,
                       error=f"http {r.status_code}: {r.text[:200]}")
            return {"ok": False, "error": f"http_{r.status_code}",
                    "raw": r.text[:500], "iterations": iteration}

        resp = r.json()
        # Spend tracking (siempre 0 USD por OAuth, pero tokens reales)
        usage = resp.get("usage", {})
        log_spend(provider="anthropic_proxy", model=model,
                  tokens_in=usage.get("input_tokens", 0),
                  tokens_out=usage.get("output_tokens", 0),
                  cost_usd=0.0,  # OAuth Max = $0
                  objective_id=str(int(start * 1000)))

        # Procesa content blocks (text + tool_use)
        tool_uses = []
        text_parts = []
        for block in resp.get("content", []):
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif block.get("type") == "tool_use":
                tool_uses.append(block)

        # Si no hay tool_use, el modelo termino
        if not tool_uses:
            final_message = " ".join(text_parts).strip()
            log_action("computer_use_done", success=1,
                       objective_summary=objective[:200],
                       elapsed_ms=int((time.time() - start) * 1000))
            return {"ok": True, "iterations": iteration,
                    "actions_executed": actions_executed,
                    "final_message": final_message[:1000],
                    "total_cost_usd": 0.0}

        # Ejecuta cada tool_use
        messages.append({"role": "assistant", "content": resp["content"]})
        tool_results = []
        for tu in tool_uses:
            tu_id = tu["id"]
            tu_input = tu.get("input", {})
            print(f"[cu it={iteration}] tool: {tu_input.get('action')}",
                  flush=True)
            result = _execute_tool_call(tu_input)
            actions_executed += 1
            log_action(
                action_type=f"cu_{tu_input.get('action', '?')}",
                target_or_command=json.dumps(tu_input)[:300],
                success=int(result.get("ok", False)),
                elapsed_ms=None,
                error=result.get("error"),
            )
            # tool_result block para enviar de vuelta
            content_list: list[dict] = []
            if result.get("screenshot_b64"):
                content_list.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png",
                                "data": result["screenshot_b64"]},
                })
            extras = {k: v for k, v in result.items()
                      if k not in ("screenshot_b64", "ok")}
            if extras:
                content_list.append({"type": "text",
                                      "text": json.dumps(extras)[:500]})
            if not content_list:
                content_list = [{"type": "text",
                                  "text": "ok" if result.get("ok") else "fail"}]
            tool_results.append({
                "type": "tool_result", "tool_use_id": tu_id,
                "content": content_list,
                "is_error": not result.get("ok", False),
            })
        messages.append({"role": "user", "content": tool_results})

    # max_iterations excedido
    log_action("computer_use_limit", success=0,
               objective_summary=objective[:200],
               error=f"max_iterations_{max_iterations}_exceeded",
               elapsed_ms=int((time.time() - start) * 1000))
    return {"ok": False, "iterations": iteration,
            "actions_executed": actions_executed,
            "error": "max_iterations_exceeded",
            "total_cost_usd": 0.0}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--objective", required=True)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--max-iterations", type=int, default=10)
    parser.add_argument("--tenant", default="default")
    args = parser.parse_args()

    from jarvis_v2.core.tenant_context import tenant_session
    from jarvis_v2.core.industry_router import route

    mask = route(args.objective, tenant_id=args.tenant)
    print(f"[bridge] industry classified: {mask['industry']}", flush=True)
    print(f"[bridge] tenant: {args.tenant}", flush=True)
    print(f"[bridge] model: {args.model}", flush=True)

    with tenant_session(args.tenant, industry=mask["industry"], mask=mask):
        r = run_agentic(
            args.objective,
            model=args.model,
            max_iterations=args.max_iterations,
            system_prompt=mask["system_prompt"],
        )
        print(json.dumps(r, ensure_ascii=False, indent=2, default=str))
