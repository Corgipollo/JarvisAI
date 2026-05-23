"""Encola el dispatch MODO INGENIERO TOP-3 (GROP/Manhua/Video-Clone)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis_v2.task_queue import add, _read, _write, _LOCK

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

def purge_bad_qid(bad: str = "550bb411fd"):
    with _LOCK:
        s = _read()
        s["pending"] = [p for p in s["pending"] if p.get("qid") != bad]
        _write(s)


if __name__ == "__main__":
    purge_bad_qid()
    qid = add(
        objective=OBJECTIVE,
        priority=10,
        source="dispatch_top3",
        tags=["audit-resolution", "grop", "manhua", "video-clone"],
    )
    print(f"qid={qid}")
    print(f"objective_len={len(OBJECTIVE)}")
    print(f"objective_head={OBJECTIVE[:120]}")
