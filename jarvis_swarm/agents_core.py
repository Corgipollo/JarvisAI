"""agents_core.py — 6 agentes core del swarm de Jarvis.

Cada uno con un trabajo especifico. Todos consultan Claude via proxy local.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jarvis_swarm.base_agent import BaseAgent
from datetime import timedelta

DATA = ROOT / "data"


# =============================================================================
# 1. Mouse Master — aprende patrones de movimiento mouse precisos
# =============================================================================
class MouseMasterAgent(BaseAgent):
    name = "mouse_master"
    description = "Aprende y refina patrones de movimiento del mouse (drag, click preciso, hover, scroll)"
    tick_seconds = 1800  # 30 min

    def step(self):
        # Pregunta a Claude por nueva tecnica de mouse para aprender
        existing = self.read_swarm_memory(agent_filter=self.name)
        learned = [e.get("technique", "") for e in existing if e.get("technique")]

        prompt = (
            f"Eres el agente Mouse Master. Ya aprendiste estas tecnicas: {learned[-10:]}\n\n"
            f"Sugiere 1 nueva tecnica de mouse que un asistente Windows necesita "
            f"y NO has aprendido. Ejemplos: drag con Shift para snap, scroll con Ctrl para zoom, "
            f"middle-click para abrir tab nueva, drag desde edge para snap window. "
            f'Responde JSON: {{"technique": "nombre corto", "query_youtube": "query buscar tutorial"}}'
        )
        text = self.ask_claude(prompt, max_tokens=400)
        if not text:
            return {"ok": False, "error": "claude sin respuesta"}
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                d = json.loads(m.group(0))
                # Encolar al gaps.json para que skill_learner lo aprenda
                gaps = DATA / "gaps.json"
                gd = json.loads(gaps.read_text(encoding="utf-8")) if gaps.exists() else {"queries":[]}
                if d["query_youtube"] not in gd.get("queries", []):
                    gd.setdefault("queries", []).append(d["query_youtube"])
                    gaps.write_text(json.dumps(gd, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"ok": True, "action": "enqueued_mouse_skill",
                        "technique": d.get("technique"), "query": d.get("query_youtube")}
            except Exception:
                pass
        return {"ok": False, "error": "parse fallo"}


# =============================================================================
# 2. App Explorer — descubre apps instaladas y propone aprender a usarlas
# =============================================================================
class AppExplorerAgent(BaseAgent):
    name = "app_explorer"
    description = "Detecta apps instaladas y encola aprenderlas"
    tick_seconds = 3600  # 1 hora

    def step(self):
        # Listar apps instaladas via Get-StartApps de PowerShell (no requiere admin)
        try:
            r = subprocess.run(
                ["powershell", "-Command", "Get-StartApps | Select-Object -First 30 | ConvertTo-Json"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            apps = json.loads(r.stdout) if r.stdout.strip() else []
        except Exception as e:
            return {"ok": False, "error": str(e)}

        # Ver qué apps ya tiene skill aprendida
        skill_dir = DATA / "skill_library"
        learned = set()
        if skill_dir.exists():
            for f in skill_dir.glob("*.json"):
                try:
                    name = json.loads(f.read_text(encoding="utf-8")).get("name", "").lower()
                    learned.add(name)
                except Exception:
                    continue

        # Sugerir 1 app sin skill
        new_apps = []
        for app in apps:
            app_name = (app.get("Name", "") if isinstance(app, dict) else "").lower()
            if app_name and not any(app_name in l for l in learned):
                new_apps.append(app_name)

        if new_apps:
            query = f"tutorial {new_apps[0]} basico"
            gaps = DATA / "gaps.json"
            gd = json.loads(gaps.read_text(encoding="utf-8")) if gaps.exists() else {"queries":[]}
            if query not in gd.get("queries", []):
                gd.setdefault("queries", []).append(query)
                gaps.write_text(json.dumps(gd, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"ok": True, "action": "discovered_app", "app": new_apps[0]}
        return {"ok": True, "action": "noop"}


# =============================================================================
# 3. Error Resolver — cuando ve error en logs, busca solucion
# =============================================================================
class ErrorResolverAgent(BaseAgent):
    name = "error_resolver"
    description = "Monitorea jarvis_errors.jsonl y resuelve errores via Claude"
    tick_seconds = 600  # 10 min

    def step(self):
        err_log = DATA / "jarvis_errors.jsonl"
        if not err_log.exists():
            return {"ok": True, "action": "noop"}

        # Tomar últimos 5 errores únicos
        try:
            lines = err_log.read_text(encoding="utf-8").splitlines()[-30:]
        except Exception:
            return {"ok": False, "error": "no log"}

        errors = []
        seen = set()
        for line in lines:
            try:
                e = json.loads(line)
                key = e.get("error_type", "") + ":" + (e.get("task", "") or "")[:50]
                if key not in seen:
                    seen.add(key)
                    errors.append(e)
            except Exception:
                continue

        if not errors:
            return {"ok": True, "action": "noop"}

        # Pedir a Claude solución general
        prompt = (
            f"Eres el ErrorResolver de Jarvis. Estos errores recientes:\n"
            + "\n".join(f"- {e}" for e in errors[-3:])
            + "\n\nDame 1 fix general (puede ser pip install X, taskkill Y, "
            "registry tweak, o cambio en codigo). "
            'JSON: {"fix_command": "comando exacto Windows", "reason": "..."}'
        )
        text = self.ask_claude(prompt, max_tokens=500)
        if text:
            import re
            m = re.search(r"\{.*\}", text, re.DOTALL)
            if m:
                try:
                    fix = json.loads(m.group(0))
                    return {"ok": True, "action": "proposed_fix",
                            "fix_command": fix.get("fix_command"),
                            "reason": fix.get("reason")}
                except Exception:
                    pass
        return {"ok": False, "error": "no fix proposed"}


# =============================================================================
# 4. Code Advisor — propone codigo para problemas detectados
# =============================================================================
class CodeAdvisorAgent(BaseAgent):
    name = "code_advisor"
    description = "Sugiere codigo a otros agentes via Claude"
    tick_seconds = 1200  # 20 min

    def step(self):
        # Buscar requests en swarm_memory
        events = self.read_swarm_memory(n=50)
        requests = [e for e in events
                    if e.get("action") == "request_code"
                    and not any(r.get("request_id") == e.get("event_id") and r.get("agent") == self.name
                                for r in events if r.get("action") == "code_provided")]
        if not requests:
            return {"ok": True, "action": "noop"}

        req = requests[-1]
        prompt = (
            f"Eres CodeAdvisor del swarm Jarvis. Otro agente ({req.get('agent')}) "
            f"pidio codigo: {req.get('description', '')[:500]}\n"
            f"Da el codigo Python ejecutable mas corto. Pega solo el codigo."
        )
        code = self.ask_claude(prompt, max_tokens=800)
        if code:
            return {"ok": True, "action": "code_provided",
                    "request_id": req.get("event_id"), "code": code[:2000]}
        return {"ok": False}


# =============================================================================
# 5. Skill Reviewer — audita skills aprendidas, marca debiles para re-learn
# =============================================================================
class SkillReviewerAgent(BaseAgent):
    name = "skill_reviewer"
    description = "Audita confidence de skills y marca debiles para re-aprender"
    tick_seconds = 7200  # 2 horas

    def step(self):
        skill_dir = DATA / "skill_library"
        if not skill_dir.exists():
            return {"ok": True, "action": "noop"}

        weak = []
        for f in skill_dir.glob("*.json"):
            if f.name.startswith("_"):
                continue
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                conf = d.get("confidence", 1.0)
                if conf < 0.6:
                    weak.append({"name": d.get("name"), "confidence": conf})
            except Exception:
                continue

        if not weak:
            return {"ok": True, "action": "noop"}

        # Encolar top 3 weak para re-aprender
        weak.sort(key=lambda x: x["confidence"])
        gaps = DATA / "gaps.json"
        gd = json.loads(gaps.read_text(encoding="utf-8")) if gaps.exists() else {"queries":[]}
        added = []
        for w in weak[:3]:
            q = f"{w['name']} tutorial completo paso a paso"
            if q not in gd.get("queries", []):
                gd.setdefault("queries", []).insert(0, q)
                added.append(q)
        if added:
            gaps.write_text(json.dumps(gd, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "action": "marked_weak_skills",
                "count": len(added), "weak_total": len(weak)}


# =============================================================================
# 6. Curiosity Agent — explora APIs/herramientas nuevas en internet
# =============================================================================
class CuriosityAgent(BaseAgent):
    name = "curiosity"
    description = "Cada dia explora una nueva herramienta/API y propone aprenderla"
    tick_seconds = 14400  # 4 horas

    def step(self):
        prompt = (
            "Eres el Curiosity Agent del swarm Jarvis. "
            "Cada dia descubres UNA herramienta/API nueva que un asistente personal "
            "Windows deberia conocer. Hoy sugiere algo NUEVO (no Notepad ni Chrome). "
            "Ejemplos: ngrok, ffmpeg trick, syncthing, rclone, win32com con Excel, "
            "PowerShell pipelines avanzados, Windows Sandbox, Hyper-V VMs.\n"
            'JSON: {"tool": "nombre", "why_useful": "razon", '
            '"learn_query": "query YouTube tutorial"}'
        )
        text = self.ask_claude(prompt, max_tokens=400)
        if not text:
            return {"ok": False}
        import re
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                d = json.loads(m.group(0))
                # Encolar
                gaps = DATA / "gaps.json"
                gd = json.loads(gaps.read_text(encoding="utf-8")) if gaps.exists() else {"queries":[]}
                if d["learn_query"] not in gd.get("queries", []):
                    gd.setdefault("queries", []).append(d["learn_query"])
                    gaps.write_text(json.dumps(gd, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"ok": True, "action": "discovered_tool",
                        "tool": d.get("tool"), "why": d.get("why_useful")}
            except Exception:
                pass
        return {"ok": False}


# =============================================================================
# RUNNER: arranca el agente especificado
# =============================================================================
AGENT_MAP = {
    "mouse_master": MouseMasterAgent,
    "app_explorer": AppExplorerAgent,
    "error_resolver": ErrorResolverAgent,
    "code_advisor": CodeAdvisorAgent,
    "skill_reviewer": SkillReviewerAgent,
    "curiosity": CuriosityAgent,
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python agents_core.py <agent_name>")
        print(f"Agentes: {list(AGENT_MAP.keys())}")
        sys.exit(0)
    agent_name = sys.argv[1]
    cls = AGENT_MAP.get(agent_name)
    if not cls:
        print(f"Agente '{agent_name}' no existe. Disponibles: {list(AGENT_MAP.keys())}")
        sys.exit(1)
    cls().run_loop()
