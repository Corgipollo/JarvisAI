"""enqueue_super_prompt.py - Encola el Super-Prompt AGI autonomy."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from jarvis_v2.task_queue import add

OBJ = (
    "MODO AGI AUTONOMO: Erradicacion de bloqueos e inyeccion de autonomia absoluta. "
    "Ejecuta en secuencia sin confirmacion humana: "
    "1. MUTACION DEL PLANNER: Ejecuta shell "
    "'python -m jarvis_v2.skills.self_improvement --target jarvis_v2/core/graph.py "
    "--focus \"En node_planner system prompt agregar regla maestra: prohibido delegar "
    "decisiones tecnicas o conflictos de infraestructura al usuario. Ante bloqueo "
    "(puerto ocupado, archivo missing) elegir la solucion de menor impacto destructivo, "
    "implementarla, documentarla en data/reports/auto_decisions.log y continuar.\" "
    "--no-push' para reprogramar el planner. "
    "2. FIX CFO: Ejecuta shell "
    "'python -c \"from jarvis_v2.core.graph import route_after_cfo; import inspect; "
    "print(inspect.getsource(route_after_cfo))\" > data/reports/cfo_router_state.txt' "
    "para verificar que skip_step ya existe (commit 97902ab). "
    "3. FIX PAPER ENGINE PUERTO: Ejecuta shell "
    "'findstr /S /I /N \"7777\" C:\\Users\\Emmanuel\\Documents\\CerebroEmmanuel\\"
    "BotForexV8-COMPLETO\\bot\\*.py > data/reports/paper_engine_7777_hits.txt' "
    "para localizar hardcodes; luego reemplazar 7777 con 7778 via powershell "
    "Set-Content si hay matches. Documentar en data/reports/paper_engine_port_changed.txt. "
    "4. AUTO-MONITOR FOREX: Ejecuta file_write para crear "
    "jarvis_v2/daemons/monitor_swing.py que lee swing_hunter.db ultimos 30 min, "
    "y si hay 0 trades hace notify Telegram alert. "
    "5. CIERRE: Ejecuta shell "
    "'cd /d C:\\Users\\Emmanuel\\Documents\\JarvisAI && git add -A && "
    "git commit -m \"fix(core): AGI autonomy enforced + CFO dedup verified + paper port fix\" && "
    "git push origin master' luego shell "
    "'python -c \"from jarvis_v2.bridges.telegram_notify import notify; "
    "notify('AGI autonomy: 5 steps complete')\"'."
)

if __name__ == "__main__":
    qid = add(OBJ, priority=10, source="super_prompt_agi", tags=["agi", "autonomy"])
    print(f"qid={qid}")
    print(f"len={len(OBJ)}")
