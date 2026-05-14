"""do.py — Wrapper rápido para ejecutar tareas con vision_executor.

Uso: python do.py <tarea en lenguaje natural>
Ej:  python do.py ordena escritorio por fecha
     python do.py abre Chrome y busca YouTube
     python do.py arrastra carpeta Downloads a Documents

Está en la raíz para evitar tipear paths con backslash/underscore
(layout teclado ESP-LAA rompe esos chars en VBoxManage keystrokes).
"""
import sys

if len(sys.argv) < 2:
    print("Uso: python do.py <tarea>")
    print("Ej:  python do.py ordena escritorio por fecha")
    sys.exit(0)

task = " ".join(sys.argv[1:])
print(f"[do.py] task: {task}")

# 1. Intentar NATIVO primero (rapido, sin screenshots)
print("[do.py] intentando metodo nativo...")
from jarvis_swarm.native_executor import execute_native
native_result = execute_native(task)

if native_result.get("ok"):
    print()
    print("=" * 60)
    print(f"NATIVO OK: {native_result.get('method')}")
    print(f"Details: {native_result}")
    print("=" * 60)
    sys.exit(0)

print(f"[do.py] nativo no aplico ({native_result.get('error', '?')}), "
      "cayendo a vision_executor...")

# 2. Fallback a vision_executor (screenshot + Claude)
from jarvis_swarm.vision_executor import execute_task
result = execute_task(task)
print()
print("=" * 60)
print(f"RESULTADO: success={result.get('success')}, steps={result.get('steps')}")
print(f"Work dir: {result.get('work_dir', '?')}")
print("=" * 60)
