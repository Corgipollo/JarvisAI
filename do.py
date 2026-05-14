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
print("[do.py] usando UNIFIED executor (cerebro NATIVO + VISION en mismo contexto)")

from jarvis_swarm.unified_executor import execute_unified
result = execute_unified(task)
print()
print("=" * 60)
print(f"RESULTADO: success={result.get('success')}, steps={result.get('steps')}")
print(f"Reason: {result.get('reason', 'OK')}")
print("=" * 60)
