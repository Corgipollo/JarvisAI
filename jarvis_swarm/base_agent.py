"""base_agent.py — Clase base para todos los 21 agentes especializados.

Cada agente hereda BaseAgent y solo necesita implementar:
  - .name: identifier
  - .tick_seconds: cada cuánto corre su loop
  - .step(): qué hace en cada iteración

BaseAgent gestiona:
  - logging
  - memoria compartida (swarm_memory.jsonl)
  - acceso a Claude via jarvis_brain
  - error handling + retry
"""
from __future__ import annotations

import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SWARM_MEMORY = ROOT / "data" / "swarm_memory.jsonl"
AGENT_LOGS = ROOT / "data" / "agent_logs"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class BaseAgent:
    """Base class para todos los agentes del swarm.

    Subclase implementa:
        def step(self) -> dict:
            return {"ok": True, "action": "...", "result": "..."}
    """
    name: str = "base"
    description: str = ""
    tick_seconds: int = 60

    def __init__(self):
        AGENT_LOGS.mkdir(parents=True, exist_ok=True)
        self.log_file = AGENT_LOGS / f"{self.name}.log"
        self.stats = {"runs": 0, "successes": 0, "failures": 0}

    def log(self, msg: str):
        line = f"[{self.name} {datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        try:
            with self.log_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def emit(self, event: dict):
        """Publica evento al swarm_memory para que otros agentes lo lean."""
        SWARM_MEMORY.parent.mkdir(parents=True, exist_ok=True)
        try:
            with SWARM_MEMORY.open("a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "agent": self.name,
                    "ts": datetime.now().isoformat(),
                    **event,
                }, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    def read_swarm_memory(self, n: int = 20, agent_filter: str | None = None) -> list[dict]:
        """Lee últimos N eventos del swarm. Útil para coordinarse."""
        if not SWARM_MEMORY.exists():
            return []
        events = []
        try:
            for line in SWARM_MEMORY.read_text(encoding="utf-8").splitlines()[-200:]:
                try:
                    e = json.loads(line)
                    if not agent_filter or e.get("agent") == agent_filter:
                        events.append(e)
                except Exception:
                    continue
        except Exception:
            pass
        return events[-n:]

    def read_unified_context(self) -> dict:
        """Lee el contexto global compartido (lo que ven TODOS los agentes).

        Cualquier agente debe llamar esto ANTES de tomar decision importante.
        Contiene: pantalla actual, tarea activa, recursos, errores recientes,
        skills count, system_brain summary, etc.
        """
        unified_file = ROOT / "data" / "unified_context.json"
        if not unified_file.exists():
            return {}
        try:
            return json.loads(unified_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def ask_claude(self, prompt: str, system: str | None = None, max_tokens: int = 1000) -> str | None:
        """Helper: pregunta a Claude via proxy local."""
        try:
            from jarvis_bridge.jarvis_brain import ask_claude
            return ask_claude(prompt, system=system or f"Eres el agente {self.name} de Jarvis. {self.description}",
                              max_tokens=max_tokens)
        except Exception as e:
            self.log(f"  ask_claude fallo: {e}")
            return None

    def step(self) -> dict:
        """Subclase override este metodo. Default: noop."""
        return {"ok": True, "action": "noop"}

    def run_loop(self):
        """Loop infinito. Llamar para arrancar el agente."""
        self.log(f"=== AGENTE {self.name} ARRANCADO (tick {self.tick_seconds}s) ===")
        self.log(f"  description: {self.description}")
        while True:
            self.stats["runs"] += 1
            try:
                result = self.step()
                if result.get("ok"):
                    self.stats["successes"] += 1
                else:
                    self.stats["failures"] += 1
                    self.log(f"  step fallo: {result.get('error', 'unknown')}")
                # Emit event si la step hizo algo interesante
                if result.get("action") and result.get("action") != "noop":
                    self.emit(result)
            except KeyboardInterrupt:
                self.log("detenido por usuario")
                break
            except Exception as e:
                self.stats["failures"] += 1
                self.log(f"  excepcion: {e}\n{traceback.format_exc()[:500]}")
            time.sleep(self.tick_seconds)


if __name__ == "__main__":
    # Demo: subclase que solo echo time
    class TickAgent(BaseAgent):
        name = "tick_demo"
        description = "Demo agent que tickea"
        tick_seconds = 10
        def step(self):
            return {"ok": True, "action": "tick", "time": datetime.now().isoformat()}
    TickAgent().run_loop()
