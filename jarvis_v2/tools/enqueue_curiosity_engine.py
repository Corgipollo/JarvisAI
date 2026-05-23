"""enqueue_curiosity_engine.py - Encola el dispatch I+D AGI."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis_v2.task_queue import add


OBJ = (
    "MODO I+D PERPETUO AGI: Instala tu propio motor de curiosidad y auto-mejora. "
    "1. Crea 'jarvis_v2/daemons/auto_researcher.py'. Debe usar deep_research "
    "para escanear arXiv/GitHub/blogs sobre OmniParser v2, agentes GUI y Anthropic "
    "Computer Use. Si encuentra mejora clara, usa 'jarvis_v2/skills/self_improvement.py' "
    "apuntando al archivo relevante para aplicar fix autonomo. "
    "2. Crea 'scripts/install_researcher.ps1' que ejecute schtasks para registrar "
    "'Jarvis_AutoResearch' con C:/CPython310/python.exe corriendo "
    "jarvis_v2/daemons/auto_researcher.py cada 12h /RL HIGHEST. "
    "3. Ejecuta el .ps1 via shell para que la tarea quede en Windows. "
    "4. git commit con mensaje 'feat(core): motor I+D perpetuo y latido de curiosidad instalado'."
)


if __name__ == "__main__":
    qid = add(OBJ, priority=10, source="curiosity_engine",
              tags=["agi", "auto-research", "self-improve"])
    print(f"qid={qid}")
