"""Debug: invoca node_planner directo con el objective top-3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

OBJECTIVE = (
    "MODO INGENIERO: Extraccion y Planificacion Automatica de Proyectos TOP-3. "
    "1. Lee los archivos MOC principales en "
    "'C:/Users/Emmanuel/Documents/CerebroEmmanuel/01-Proyectos/GROP-Ecommerce/MOC - GROP Ecommerce.md', "
    "'C:/Users/Emmanuel/Documents/CerebroEmmanuel/01-Proyectos/Manhua-Narrado/MOC - Manhua Narrado.md' "
    "y los .md de 'C:/Users/Emmanuel/Documents/CerebroEmmanuel/01-Proyectos/Video-Clone-Style/'. "
    "2. Aisla las lineas con 'TODO', 'pendiente' o 'FIXME' en cada uno. "
    "3. Invoca la API directa de Gemini/Claude (NO web UI) pasandole el contexto de estos "
    "TODOs y pidele un plan de resolucion tecnica concreto y accionable para cada uno de "
    "los tres proyectos (steps tecnicos, archivos a tocar, comandos a correr). "
    "4. Guarda las tres hojas de ruta resultantes como markdown en "
    "'C:/Users/Emmanuel/Documents/JarvisAI/data/reports/roadmap_grop.md', "
    "'C:/Users/Emmanuel/Documents/JarvisAI/data/reports/roadmap_manhua.md' y "
    "'C:/Users/Emmanuel/Documents/JarvisAI/data/reports/roadmap_video_clone.md'."
)

from jarvis_v2.core.graph import node_planner, count_explicit_steps

n = count_explicit_steps(OBJECTIVE)
print(f"explicit_n detectado: {n}")
state = {"objective": OBJECTIVE, "cerebro_context": "(contexto vacio para debug)"}
result = node_planner(state)
print(f"plan_len: {len(result.get('plan', []))}")
print(f"last_error: {result.get('last_error')}")
print(f"messages: {result.get('messages')}")
import json
print("---PLAN STEPS---")
for i, s in enumerate(result.get("plan", [])):
    print(f"  {i}: {json.dumps(s, ensure_ascii=False, default=str)[:200]}")
