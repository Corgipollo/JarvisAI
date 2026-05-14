"""meta_agent.py — EL CEREBRO QUE CREA OTROS CEREBROS.

Loop:
  1. Cada 30 min analiza el estado del swarm (skills aprendidas, errores, gaps)
  2. Pregunta a Claude: que NUEVO agente especializado nos hace falta?
  3. Claude genera el codigo Python completo del nuevo agente
  4. meta_agent escribe el .py en jarvis_swarm/auto_agents/<name>.py
  5. Lo lanza como subprocess
  6. Lo registra en swarm_registry.json
  7. Si un agente falla repetido, meta_agent le pide a Claude el fix y se
     auto-modifica (sobrescribe el .py)

Asi el swarm CRECE solo, sin que Emmanuel escriba codigo.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

AUTO_AGENTS_DIR = ROOT / "jarvis_swarm" / "auto_agents"
REGISTRY = ROOT / "data" / "swarm_registry.json"


class MetaAgent(BaseAgent):
    name = "meta_agent"
    description = "Crea y modifica otros agentes del swarm automaticamente"
    tick_seconds = 1800  # 30 min

    def __init__(self):
        super().__init__()
        AUTO_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
        (AUTO_AGENTS_DIR / "__init__.py").touch()
        self.registry = self._load_registry()

    def _load_registry(self) -> dict:
        if REGISTRY.exists():
            try:
                return json.loads(REGISTRY.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"agents": [], "spawn_count": 0}

    def _save_registry(self):
        REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY.write_text(json.dumps(self.registry, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    def _list_existing_agents(self) -> list[str]:
        existing = []
        for p in AUTO_AGENTS_DIR.glob("*.py"):
            if p.name == "__init__.py":
                continue
            existing.append(p.stem)
        return existing

    def design_new_agent(self) -> dict | None:
        """Pide a Claude que diseñe un nuevo agente especializado."""
        existing = self._list_existing_agents()
        core_agents = ["mouse_master", "app_explorer", "error_resolver",
                       "code_advisor", "skill_reviewer", "curiosity",
                       "dialog_guardian", "watchdog", "self_optimizer"]
        all_known = list(set(existing + core_agents))

        prompt = (
            f"Eres el META-AGENT del swarm Jarvis. Diseñas nuevos agentes especializados.\n\n"
            f"Agentes ya existentes ({len(all_known)}): {all_known[:30]}\n\n"
            f"Diseña UN nuevo agente especializado que el swarm NO tiene. "
            f"Sé creativo: puede ser un agente que monitorea uso de disco, "
            f"que aprende keyboard layouts, que detecta apps colgadas, que "
            f"organiza Downloads, que limpia temp files, que monitorea network, "
            f"que aprende patrones de TUS apps, etc.\n\n"
            f'Responde JSON estricto:\n'
            f'{{\n'
            f'  "name": "snake_case_agent_name",\n'
            f'  "description": "1 linea de que hace",\n'
            f'  "tick_seconds": numero entre 300 y 86400,\n'
            f'  "step_logic": "descripcion en 3-5 frases de QUE hace cada step y como"\n'
            f'}}\n'
            f"NO devuelvas codigo, solo el diseño."
        )

        text = self.ask_claude(prompt, max_tokens=600)
        if not text:
            return None
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            return None
        try:
            d = json.loads(m.group(0))
            # Verificar que no duplica
            if d.get("name") in all_known:
                self.log(f"  ya existe '{d['name']}', re-diseñando proximo tick")
                return None
            return d
        except Exception:
            return None

    def generate_agent_code(self, design: dict) -> str | None:
        """Pide a Claude que genere el codigo Python del agente."""
        prompt = (
            f"Genera el codigo Python COMPLETO de este agente del swarm Jarvis:\n\n"
            f"name: {design['name']}\n"
            f"description: {design['description']}\n"
            f"tick_seconds: {design['tick_seconds']}\n"
            f"step_logic: {design['step_logic']}\n\n"
            f"Debe seguir EXACTAMENTE esta plantilla (subclase BaseAgent):\n\n"
            f"```python\n"
            f'"""{design["name"]}.py — descripcion."""\n'
            f"from __future__ import annotations\n"
            f"import json, sys, time, subprocess\n"
            f"from datetime import datetime\n"
            f"from pathlib import Path\n"
            f"ROOT = Path(__file__).resolve().parents[2]\n"
            f"sys.path.insert(0, str(ROOT))\n"
            f"from jarvis_swarm.base_agent import BaseAgent\n\n"
            f"class Agent(BaseAgent):\n"
            f"    name = \"{design['name']}\"\n"
            f"    description = \"{design['description']}\"\n"
            f"    tick_seconds = {design['tick_seconds']}\n\n"
            f"    def step(self):\n"
            f"        # implementar step_logic aqui\n"
            f"        # Acceso a Claude: self.ask_claude(prompt)\n"
            f"        # Emit eventos: return {{\"ok\": True, \"action\": \"...\"}}\n"
            f"        # Leer memoria swarm: self.read_swarm_memory(n=10)\n"
            f"        return {{\"ok\": True, \"action\": \"noop\"}}\n\n"
            f"if __name__ == \"__main__\":\n"
            f"    Agent().run_loop()\n"
            f"```\n\n"
            f"Genera el codigo REAL implementando step_logic. Max 60 lineas. "
            f"Solo el codigo Python, sin markdown, sin explicaciones."
        )

        code = self.ask_claude(prompt, max_tokens=2000)
        if not code:
            return None
        # Quitar code fences si las hay
        code = re.sub(r"^```(?:python)?\n", "", code.strip())
        code = re.sub(r"\n```$", "", code)
        # Validacion minima: debe contener "class Agent" y "BaseAgent"
        if "class Agent" not in code or "BaseAgent" not in code:
            self.log("  codigo invalido: falta class Agent o BaseAgent")
            return None
        return code

    def spawn_agent(self, design: dict, code: str) -> bool:
        """Guarda el agente y lo lanza en background."""
        agent_file = AUTO_AGENTS_DIR / f"{design['name']}.py"
        try:
            agent_file.write_text(code, encoding="utf-8")
            self.log(f"  agente escrito: {agent_file.name}")
        except Exception as e:
            self.log(f"  ERR escribir: {e}")
            return False

        # Lanzar como subprocess
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            proc = subprocess.Popen(
                [sys.executable, str(agent_file)],
                cwd=str(ROOT), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
            )
            self.log(f"  agente lanzado: pid={proc.pid}")
            # Registrar
            self.registry["agents"].append({
                "name": design["name"],
                "description": design["description"],
                "tick_seconds": design["tick_seconds"],
                "spawned_at": datetime.now().isoformat(),
                "pid": proc.pid,
                "file": str(agent_file),
            })
            self.registry["spawn_count"] += 1
            self._save_registry()
            return True
        except Exception as e:
            self.log(f"  ERR lanzar: {e}")
            return False

    def step(self):
        # Diseñar nuevo agente
        design = self.design_new_agent()
        if not design:
            return {"ok": True, "action": "noop", "reason": "no design"}

        self.log(f"  diseño nuevo agente: {design['name']} - {design['description']}")
        code = self.generate_agent_code(design)
        if not code:
            return {"ok": False, "error": "code gen fail", "design": design}

        ok = self.spawn_agent(design, code)
        return {"ok": ok, "action": "spawned_agent",
                "name": design["name"], "description": design["description"]}


if __name__ == "__main__":
    MetaAgent().run_loop()
