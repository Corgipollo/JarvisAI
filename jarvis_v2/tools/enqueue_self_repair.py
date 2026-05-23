"""enqueue_self_repair.py - dispara dispatch MODO ARQUITECTO GOD-MODE.

Mete en la queue el objetivo que ordena a Jarvis abrirse a si mismo y
parchear el planner anti-condensacion. NO modifica codigo a mano: deja
que Jarvis use su propia skill self_improvement.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from jarvis_v2.task_queue import add


OBJECTIVE = (
    "MODO ARQUITECTO GOD-MODE: Auto-reparacion estructural del Planner. "
    "1. Ejecuta shell 'python -m jarvis_v2.skills.self_improvement \"anti-condensacion planner: detectar steps numerados explicitos 1. 2. 3. en objective y forzar plan.steps >= N\"' para invocar tu ciclo de auto-mejora con focus especifico sobre el bug del planner. "
    "2. Si self_improvement no eligio jarvis_v2/core/graph.py como target (porque pick_target es random), ejecuta shell 'python -c \"from jarvis_v2.skills.self_improvement import propose_improvement, apply_and_validate, commit_and_push; from pathlib import Path; ROOT = Path(r\\\"C:/Users/Emmanuel/Documents/JarvisAI\\\"); t = ROOT/\\\"jarvis_v2/core/graph.py\\\"; p = propose_improvement(t, focus=\\\"Anti-Condensation Patch: en node_planner, despues de plan_obj = llm_structured(...) agregar validacion que cuente steps numerados explicitos en objective (regex \\\\d+\\\\.) y si plan_obj.steps tiene menos elementos, hacer retry forzado con prompt mas explicito. Devolver new_content del archivo completo.\\\"); import json; print(json.dumps(p, default=str)[:500])\"' para forzar el target especifico. "
    "3. Verifica el archivo modificado con shell 'python -m py_compile jarvis_v2/core/graph.py' y solo si compila ejecuta shell 'cd /d C:\\\\Users\\\\Emmanuel\\\\Documents\\\\JarvisAI && git add jarvis_v2/core/graph.py && git commit -m \"fix(planner): anti-condensation patch - reject plans with steps<N when objective enumerates N sub-tasks\" && git push origin master'. "
    "4. Reporta status final escribiendo a shell 'echo OK > C:\\\\Users\\\\Emmanuel\\\\Documents\\\\JarvisAI\\\\data\\\\reports\\\\self_repair_status.txt' o 'echo FAIL'."
)


if __name__ == "__main__":
    qid = add(
        objective=OBJECTIVE,
        priority=10,
        source="dispatch_self_repair",
        tags=["self-repair", "anti-condensation", "planner-fix"],
    )
    print(f"qid={qid}")
    print(f"len={len(OBJECTIVE)}")
