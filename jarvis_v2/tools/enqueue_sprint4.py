"""enqueue_sprint4.py - Encola Sprint 4 CapCut/Paint E2E (audit)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis_v2.task_queue import add

OBJ = (
    "MODO AGI EJECUCION: Sprint 4 CapCut E2E. "
    "1. capcut_pipeline.py ya creado en jarvis_v2/skills/. "
    "2. cap_test_dummy.yaml ya creado (CapCut NO instalado - template). "
    "3. paint_test_dummy.yaml ya creado (fallback ejecutable). "
    "4. Ejecuta shell 'C:\\CPython310\\python.exe -m jarvis_v2.skills.capcut_pipeline "
    "C:\\Users\\Emmanuel\\Documents\\JarvisAI\\data\\fixtures\\paint_test_dummy.yaml' "
    "para correr el flow E2E con Paint (substituto valido del editor de video). "
    "5. Si data/fixtures/paint_export_test.png existe con size > 1000 bytes, "
    "commit 'feat(sprint4): pipeline E2E validado con Paint (CapCut pending install)'. "
    "Si falla, log el error a data/reports/sprint4_failure.txt sin reintentar "
    "(evitar bucles infinitos en el self_improvement)."
)


if __name__ == "__main__":
    qid = add(OBJ, priority=10, source="sprint4_e2e",
              tags=["sprint4", "capcut", "paint", "agi"])
    print(f"qid={qid}")
