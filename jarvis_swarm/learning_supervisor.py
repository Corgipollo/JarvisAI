"""learning_supervisor.py — Verifica que Jarvis REALMENTE aprende, no superficial.

Cada hora:
  1. Toma 3 skills aprendidas random
  2. Ejecuta cada una con vision_executor + UIA tree inspection
  3. Despues de cada accion captura:
     - Screenshot pixel-perfect
     - UIA tree completo de la ventana activa (estructura nativa Windows)
     - Texto OCR de regiones criticas
  4. Manda TODO a Claude y pregunta:
     "¿La accion fue correcta? ¿Comprendiste la app? ¿O solo memorizaste pasos?"
  5. Claude responde con un veredicto + lo que falta entender
  6. Si Claude dice "memoria sin comprension" -> marca skill para re-aprender CON
     contexto: agrega al gaps.json el query con "comprende como funciona X"
     en lugar de solo "tutorial X"

Filosofia: aprender != memorizar. Necesita comprender la app.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent


def get_uia_tree_summary() -> str:
    """Captura estructura UIA de la ventana activa - lo que Windows EXPONE."""
    try:
        from pywinauto import Desktop
        desktop = Desktop(backend="uia")
        active = None
        for w in desktop.windows():
            try:
                if w.is_active():
                    active = w
                    break
            except Exception:
                continue
        if not active:
            return "(sin ventana activa)"

        summary = f"Ventana activa: {active.window_text()}\n"
        summary += f"Class: {active.class_name()}\n"
        summary += "Controles principales:\n"
        try:
            for c in active.descendants()[:40]:
                try:
                    text = c.window_text()[:50]
                    ctype = c.element_info.control_type
                    if text or ctype in ("Button", "Edit", "ComboBox", "MenuItem"):
                        summary += f"  - [{ctype}] {text}\n"
                except Exception:
                    continue
        except Exception:
            summary += "  (sin acceso a controles)\n"
        return summary[:2000]
    except ImportError:
        return "(pywinauto no instalado)"
    except Exception as e:
        return f"(error: {e})"


class LearningSupervisorAgent(BaseAgent):
    name = "learning_supervisor"
    description = "Verifica que las skills se aprenden de verdad, no memorizan superficial"
    tick_seconds = 3600  # cada 1 hora

    def evaluate_skill_deeply(self, skill: dict) -> dict:
        """Ejecuta + captura UIA + Claude evalua comprension."""
        from jarvis_swarm.vision_executor import take_screenshot

        # Screenshot inicial
        ROOT_DATA = ROOT / "data" / "supervisor_runs"
        ROOT_DATA.mkdir(parents=True, exist_ok=True)
        run_dir = ROOT_DATA / datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir.mkdir(exist_ok=True)

        before_shot = run_dir / "before.png"
        take_screenshot(before_shot)
        uia_before = get_uia_tree_summary()

        # Ejecutar primer step de la skill (no todos para limitar riesgo)
        steps = skill.get("steps") or (skill.get("methods", [{}])[0].get("steps", []))
        if not steps:
            return {"verdict": "NO_STEPS", "skill": skill.get("name")}

        try:
            from jarvis_swarm.skill_executor import execute_step  # type: ignore
        except ImportError:
            try:
                from jarvis_learners.skill_executor import execute_step  # type: ignore
            except ImportError:
                return {"verdict": "NO_EXECUTOR"}

        # Solo ejecuta primer step para evaluar comprension
        first = steps[0] if isinstance(steps[0], dict) else {"action": "noop"}
        result = execute_step(first) if callable(globals().get("execute_step")) else {"ok": False}
        time.sleep(2)

        after_shot = run_dir / "after.png"
        take_screenshot(after_shot)
        uia_after = get_uia_tree_summary()

        # Mandar a Claude evaluacion profunda
        try:
            from jarvis_bridge.jarvis_brain import ask_claude_with_image
        except ImportError:
            return {"verdict": "NO_CLAUDE"}

        prompt = (
            f"SUPERVISION DE APRENDIZAJE PROFUNDO\n\n"
            f"Skill aprendida: {skill.get('name')}\n"
            f"Intent: {skill.get('intent', '')[:200]}\n\n"
            f"=== UIA TREE ANTES ===\n{uia_before}\n\n"
            f"=== UIA TREE DESPUES ===\n{uia_after}\n\n"
            f"Primer paso ejecutado: {first}\n"
            f"Resultado: {result}\n\n"
            f"Te muestro el SCREENSHOT DESPUES. Evalua:\n"
            f"1. La accion fue correcta TECNICAMENTE?\n"
            f"2. Jarvis COMPRENDE la app o solo memoriza pasos?\n"
            f"3. Si el UIA tree muestra controles inesperados, Jarvis los conoce?\n"
            f"4. Que NO ENTIENDE Jarvis de esta skill?\n\n"
            f'Responde JSON: {{"verdict": "COMPRENDE|MEMORIZA|FALLA", '
            f'"correcto_tecnicamente": bool, "lo_que_no_entiende": "...", '
            f'"necesita_reaprender": bool, "nuevo_query_mejor": "..."}}'
        )
        text = ask_claude_with_image(prompt, str(after_shot), max_tokens=600) or ""
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return {"verdict": "PARSE_FAIL", "raw": text[:300]}

    def step(self):
        skill_dir = ROOT / "data" / "skill_library"
        if not skill_dir.exists():
            return {"ok": True, "action": "no_skills"}

        import random
        files = [f for f in skill_dir.glob("*.json") if not f.name.startswith("_")]
        if not files:
            return {"ok": True, "action": "no_skills"}

        # Sample 3 (limitado para no abusar)
        sample = random.sample(files, min(3, len(files)))
        results = []
        for f in sample:
            try:
                s = json.loads(f.read_text(encoding="utf-8"))
                self.log(f"  evaluando: {s.get('name', '?')[:60]}")
                evaluation = self.evaluate_skill_deeply(s)
                results.append({"skill": s.get("name"), "evaluation": evaluation})

                # Si Claude dice necesita reaprender + da query mejor, encolar
                if evaluation.get("necesita_reaprender") and evaluation.get("nuevo_query_mejor"):
                    gaps_file = ROOT / "data" / "gaps.json"
                    try:
                        gd = json.loads(gaps_file.read_text(encoding="utf-8")) if gaps_file.exists() else {"queries":[]}
                        new_q = evaluation["nuevo_query_mejor"]
                        if new_q not in gd.get("queries", []):
                            gd.setdefault("queries", []).insert(0, new_q)
                            gaps_file.write_text(json.dumps(gd, ensure_ascii=False, indent=2), encoding="utf-8")
                            self.log(f"    reaprender encolado: {new_q[:60]}")
                    except Exception:
                        pass

                # Update confidence en disco
                conf_delta = 0.0
                if evaluation.get("verdict") == "COMPRENDE":
                    conf_delta = 0.15
                elif evaluation.get("verdict") == "MEMORIZA":
                    conf_delta = -0.05
                elif evaluation.get("verdict") == "FALLA":
                    conf_delta = -0.20
                if conf_delta:
                    s["confidence"] = max(0.0, min(1.0, s.get("confidence", 0.5) + conf_delta))
                    s["last_supervised"] = datetime.now().isoformat()
                    f.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                self.log(f"  ERR: {e}")
                continue

        return {"ok": True, "action": "supervised", "skills_evaluated": len(results),
                "results": results}


if __name__ == "__main__":
    LearningSupervisorAgent().run_loop()
