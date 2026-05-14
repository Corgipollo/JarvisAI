"""auto_practice.py — Agente que PRACTICA skills aprendidas mover mouse archivos etc.

Cada 30 min:
  1. Elige una skill aleatoria de data/skill_library/
  2. La ejecuta REAL con vision_executor (loop ver-pensar-actuar)
  3. Si funciona: bumpa confidence +0.1
  4. Si falla: marca para re-aprender + log

Es el GAP que faltaba: Jarvis tenia 202 skills PERO nunca las USABA.
Este agente PRACTICA. Como un humano que aprende mirando tutoriales pero
necesita HACERLO para fijar la memoria muscular.
"""
from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent

SKILLS_DIR = ROOT / "data" / "skill_library"
PRACTICE_LOG = ROOT / "data" / "practice_log.jsonl"


class AutoPracticeAgent(BaseAgent):
    name = "auto_practice"
    description = "Practica skills aprendidas ejecutandolas con pyautogui"
    tick_seconds = 1800  # cada 30 min

    def __init__(self):
        super().__init__()
        # Practicas SAFE primero (skills sin riesgo)
        self.safe_categories = [
            "mouse", "open", "close", "move", "click",
            "calculator", "notepad", "screenshot", "snipping",
            "telegram", "obsidian", "discord", "chrome", "edge",
            "copy", "paste", "shortcut",
        ]

    def is_safe_skill(self, skill: dict) -> bool:
        """Solo practica skills 'seguras' (no formatear disco, no rm -rf)."""
        name = (skill.get("name", "") + " " + skill.get("intent", "")).lower()
        # Categorias permitidas
        if any(cat in name for cat in self.safe_categories):
            return True
        return False

    def pick_random_skill(self) -> dict | None:
        if not SKILLS_DIR.exists():
            return None
        candidates = []
        for f in SKILLS_DIR.glob("*.json"):
            if f.name.startswith("_"):
                continue
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
                if self.is_safe_skill(s):
                    # Prefer skills bajo-practicadas
                    times_practiced = s.get("executions_attempted", 0)
                    confidence = s.get("confidence", 0.5)
                    # Score: mas alto = mas necesita practica
                    score = (1 - confidence) + 1.0 / (1 + times_practiced)
                    candidates.append((score, f, s))
            except Exception:
                continue
        if not candidates:
            return None
        # Sample weighted al score (no top-1)
        candidates.sort(key=lambda x: -x[0])
        top10 = candidates[:10]
        chosen = random.choice(top10)
        return {"file": chosen[1], "skill": chosen[2]}

    def execute_skill(self, skill: dict) -> dict:
        """Usa vision_executor para ejecutar la skill como tarea."""
        try:
            from jarvis_swarm.vision_executor import execute_task
        except ImportError:
            return {"success": False, "error": "vision_executor no disponible"}

        task = skill.get("name", "")
        if not task:
            return {"success": False, "error": "skill sin name"}

        self.log(f"  ejecutando: {task[:60]}")
        try:
            result = execute_task(task, max_steps=8)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_skill_metrics(self, skill_file: Path, success: bool):
        try:
            d = json.loads(skill_file.read_text(encoding="utf-8"))
            d["executions_attempted"] = d.get("executions_attempted", 0) + 1
            if success:
                d["executions_successful"] = d.get("executions_successful", 0) + 1
                d["confidence"] = min(1.0, d.get("confidence", 0.5) + 0.1)
            else:
                d["confidence"] = max(0.0, d.get("confidence", 0.5) - 0.05)
            d["last_practice"] = datetime.now().isoformat()
            skill_file.write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        except Exception:
            pass

    def step(self):
        picked = self.pick_random_skill()
        if not picked:
            return {"ok": True, "action": "no_safe_skills"}

        self.log(f"=== PRACTICA: {picked['skill'].get('name', '?')} ===")
        result = self.execute_skill(picked["skill"])
        success = result.get("success", False)
        self.update_skill_metrics(picked["file"], success)

        # Log
        PRACTICE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with PRACTICE_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now().isoformat(),
                "skill": picked["skill"].get("name"),
                "success": success,
                "result": str(result)[:300],
            }, ensure_ascii=False) + "\n")

        return {"ok": True, "action": "practiced",
                "skill": picked["skill"].get("name"), "success": success}


if __name__ == "__main__":
    AutoPracticeAgent().run_loop()
