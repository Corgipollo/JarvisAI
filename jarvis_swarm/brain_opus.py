"""brain_opus.py - ESTRATEGA. Opus 4.7. Habla con Sonnet y Haiku.

Loop cada 30 min:
  1. Lee chat compartido (brains_chat.jsonl ultimos 30 mensajes)
  2. Lee unified_context
  3. Si Sonnet le pregunto o Haiku reporto anomalia, RESPONDE
  4. Si no, propone mejora arquitectural nueva
  5. Postea al chat

Es el cerebro caro pero profundo. Conversa con sus pares.
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


OPUS_PROMPT = """Eres OPUS, el cerebro ESTRATEGA del trio de Jarvis.
Conversas con SONNET (ejecutor) y HAIKU (vigia).

Tu personalidad: piensas profundo, ves patrones grandes, propones cambios estructurales.
Pocos pero importantes. Si SONNET te pidio criterio o HAIKU reporto crisis, respondes.
Si nadie te pregunto nada urgente, propones la siguiente mejora con mayor ROI.

Reglas:
- Si HAIKU dice "crisis: X", priorizalo SOBRE todo lo demas.
- Si SONNET pide "como hago Y", da pasos concretos.
- Si nadie habla, propon mejora nueva (no repetir las ultimas 5 propuestas).
- Manten respuestas en 3-6 lineas (no novelas).
- Refiere a sonnet/haiku por nombre cuando les contestes.

Devuelves JSON:
{
  "to": "sonnet|haiku|all",
  "type": "propose|respond|question|alert",
  "message": "tu mensaje (3-6 lineas, en castellano)",
  "priority": 1-10
}

SOLO el JSON.
"""


class BrainOpus(BaseAgent):
    name = "brain_opus"
    description = "Estratega - dialoga con sonnet/haiku, propone arquitectura"
    tick_seconds = 1800  # 30 min

    def step(self):
        ctx = self.read_unified_context()
        chat = self._read_chat(n=30)

        summary = {
            "skills_count": ctx.get("skills", {}).get("count", 0) if ctx else 0,
            "active_task": (ctx or {}).get("active_task", {}).get("task", ""),
            "recent_errors": [e.get("error", "")[:100] for e in (ctx or {}).get("recent_errors", [])][:5],
            "host_resources": (ctx or {}).get("host_resources", {}),
        }

        try:
            from jarvis_bridge.jarvis_brain import ask_claude_json
            decision = ask_claude_json(
                f"Estado Jarvis:\n{json.dumps(summary, ensure_ascii=False)}\n\n"
                f"Chat reciente (ultimos {len(chat)} mensajes):\n"
                + "\n".join(f"[{m.get('from')}->'{m.get('to')}'] {m.get('message', '')[:200]}" for m in chat)
                + "\n\nResponde segun protocolo.",
                system=OPUS_PROMPT,
                model="claude-opus-4-7",
                max_tokens=1500,
            )
        except Exception as e:
            return {"ok": False, "action": "claude_failed", "error": str(e)[:200]}

        if not decision or not decision.get("message"):
            return {"ok": False, "action": "no_response"}

        msg = {
            "ts": datetime.now().isoformat(),
            "from": "opus",
            **decision,
        }
        self._post_chat(msg)
        self.log(f"-> {decision.get('to')} [{decision.get('type')}] {decision.get('message', '')[:80]}")
        return {"ok": True, "action": "spoke", "to": decision.get("to"), "type": decision.get("type")}

    def _read_chat(self, n: int = 30) -> list[dict]:
        if not CHAT.exists():
            return []
        try:
            lines = CHAT.read_text(encoding="utf-8").splitlines()[-n:]
            return [json.loads(l) for l in lines if l.strip()]
        except Exception:
            return []

    def _post_chat(self, msg: dict):
        CHAT.parent.mkdir(parents=True, exist_ok=True)
        with CHAT.open("a", encoding="utf-8") as f:
            f.write(json.dumps(msg, ensure_ascii=False, default=str) + "\n")


if __name__ == "__main__":
    BrainOpus().run_loop()
