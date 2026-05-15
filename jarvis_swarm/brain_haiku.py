"""brain_haiku.py - VIGIA. Haiku 4.5. Dialoga con Opus y Sonnet.

Loop cada 90s:
  1. Lee unified_context (pantalla, errores recientes, recursos)
  2. Si detecta anomalia (dialog stuck, RAM alta, error pattern), ALERTA
  3. Si todo OK, observa silenciosamente (no spam)
  4. Postea al chat cuando hay algo que decir
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

DATA = ROOT / "data"
CHAT = DATA / "brains_chat.jsonl"
LAST_ALERT = DATA / "haiku_last_alert.json"


HAIKU_PROMPT = """Eres HAIKU, el cerebro VIGIA del trio de Jarvis.
Conversas con OPUS (estratega) y SONNET (ejecutor).

Tu personalidad: rapido, alerta, escaneas constantemente. Reportas anomalias
en 1-2 lineas. NO propones soluciones (eso es trabajo de Opus/Sonnet). NO spam:
si nada cambia, te quedas callado.

Reglas:
- Si pantalla congelada >5min en mismo estado: ALERT "screen_frozen".
- Si RAM > 90%: ALERT "ram_critical".
- Si >5 errores recientes mismo tipo: ALERT "error_pattern: X".
- Si SONNET pregunto algo: contesta breve con dato observado.
- Si todo OK Y no hay nuevo dato: type=silent (no postea).

Devuelves JSON:
{
  "to": "opus|sonnet|all|none",
  "type": "alert|observation|reply|silent",
  "message": "1-2 lineas",
  "urgency": 1-5
}

SOLO el JSON. type=silent si nada que decir.
"""


class BrainHaiku(BaseAgent):
    name = "brain_haiku"
    description = "Vigia - alerta anomalias rapidamente"
    tick_seconds = 90  # cada 1.5 min

    def step(self):
        ctx = self.read_unified_context()
        if not ctx:
            return {"ok": False, "action": "no_context"}

        observations = {
            "active_window": ctx.get("screen", {}).get("active_window", "")[:80],
            "context_desc": ctx.get("screen", {}).get("context_desc", "")[:200],
            "ram_pct": ctx.get("host_resources", {}).get("ram_pct", 0),
            "cpu_pct": ctx.get("host_resources", {}).get("cpu_pct", 0),
            "disk_free_gb": ctx.get("host_resources", {}).get("disk_free_gb", 0),
            "recent_error_count": len(ctx.get("recent_errors", [])),
            "recent_errors_top3": [e.get("error", "")[:80] for e in ctx.get("recent_errors", [])][:3],
            "swarm_procs_count": len(ctx.get("swarm_processes", [])),
        }

        try:
            from jarvis_bridge.jarvis_brain import ask_claude_json
            decision = ask_claude_json(
                f"Observaciones actuales:\n{json.dumps(observations, ensure_ascii=False)}\n\n"
                "Responde segun protocolo. Si nada que reportar, type=silent.",
                system=HAIKU_PROMPT,
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
            )
        except Exception as e:
            return {"ok": False, "action": "claude_failed", "error": str(e)[:200]}

        if not decision or decision.get("type") == "silent":
            return {"ok": True, "action": "silent"}

        msg = {
            "ts": datetime.now().isoformat(),
            "from": "haiku",
            **decision,
        }
        self._post_chat(msg)
        self.log(f"-> {decision.get('to')} [{decision.get('type')} u{decision.get('urgency')}] {decision.get('message', '')[:80]}")
        return {"ok": True, "action": "spoke", "to": decision.get("to"), "type": decision.get("type")}

    def _post_chat(self, msg: dict):
        CHAT.parent.mkdir(parents=True, exist_ok=True)
        with CHAT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    BrainHaiku().run_loop()
