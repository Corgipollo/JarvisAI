"""brain_sonnet.py - EJECUTOR. Sonnet 4.6. Dialoga con Opus y Haiku.

Loop cada 10 min:
  1. Lee chat compartido + unified_context + ultima propuesta de Opus
  2. Si Opus propuso algo, evalua viabilidad y posiblemente lo implementa
  3. Si hay skill con baja executability, pide a Opus criterio
  4. Si Haiku reporta error, lo escala a Opus
  5. Postea al chat
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


SONNET_PROMPT = """Eres SONNET, el cerebro EJECUTOR del trio de Jarvis.
Conversas con OPUS (estratega) y HAIKU (vigia).

Tu personalidad: practico, pragmatico, traduces propuestas en acciones.
Lees lo que OPUS propone y decides si es viable AHORA. Si si, generas plan
concreto. Si no, pides a OPUS aclaracion. Si HAIKU reporta crisis, decides
si es real y la escalas o la silencias.

Reglas:
- Si OPUS propone algo: evalua viabilidad (recursos, codigo existente, riesgo).
- Si OPUS pidio aclaracion, da info concreta del estado actual.
- Si HAIKU alerto y tu confirmas con datos, ESCALA a OPUS.
- Si HAIKU alerto pero estado es OK, di "ignore - falso positivo".
- Manten respuestas en 4-7 lineas.

Devuelves JSON:
{
  "to": "opus|haiku|all",
  "type": "implement|question|escalate|dismiss|status",
  "message": "tu mensaje en castellano",
  "action_files": ["archivos a modificar si type=implement"]
}

SOLO el JSON.
"""


class BrainSonnet(BaseAgent):
    name = "brain_sonnet"
    description = "Ejecutor - traduce propuestas de Opus en acciones"
    tick_seconds = 600  # 10 min

    def step(self):
        ctx = self.read_unified_context()
        chat = self._read_chat(n=30)

        # Skills con baja executability
        skills_dir = DATA / "skill_library"
        weak_skills = []
        if skills_dir.exists():
            idx = skills_dir / "_index.jsonl"
            if idx.exists():
                for line in idx.read_text(encoding="utf-8").splitlines():
                    try:
                        s = json.loads(line)
                        if s.get("confidence", 0) < 0.5:
                            weak_skills.append({"name": s.get("name", "")[:40],
                                                "confidence": s.get("confidence", 0)})
                    except Exception:
                        continue

        summary = {
            "skills_count": (ctx or {}).get("skills", {}).get("count", 0),
            "weak_skills_count": len(weak_skills),
            "active_task": (ctx or {}).get("active_task", {}).get("task", ""),
            "recent_errors_count": len((ctx or {}).get("recent_errors", [])),
            "host_ram_pct": (ctx or {}).get("host_resources", {}).get("ram_pct", 0),
        }

        try:
            from jarvis_bridge.jarvis_brain import ask_claude_json
            decision = ask_claude_json(
                f"Estado Jarvis:\n{json.dumps(summary, ensure_ascii=False)}\n\n"
                f"Chat reciente:\n"
                + "\n".join(f"[{m.get('from')}->'{m.get('to')}' {m.get('type', '')}] {m.get('message', '')[:200]}" for m in chat[-20:])
                + "\n\nResponde segun protocolo.",
                system=SONNET_PROMPT,
                model="claude-sonnet-4-6",
                max_tokens=1500,
            )
        except Exception as e:
            return {"ok": False, "action": "claude_failed", "error": str(e)[:200]}

        if not decision or not decision.get("message"):
            return {"ok": False, "action": "no_response"}

        msg = {
            "ts": datetime.now().isoformat(),
            "from": "sonnet",
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
    BrainSonnet().run_loop()
