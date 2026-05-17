"""dispatch_test.py - Manual dispatch al API local para testear sin esperar heartbeat.

Uso: python -m jarvis_v2.dispatch_test
"""
import json
import os
import sys
import requests

API_URL = os.environ.get("JARVIS_API_URL_LOCAL", "http://127.0.0.1:5000")
TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")

OBJECTIVE = (
    "MODO BOOTSTRAPPING ESTRICTO: Presupuesto $0. No uses APIs de paga ni servicios "
    "externos. Genera un script Python local en C:/Jarvis/workspace/ que cree "
    "una estructura de carpetas de proyecto (idea/, scripts/, output/) y un archivo "
    "marketing_plan.md con un plan de marketing organico para redes sociales "
    "(LinkedIn, Twitter, Reddit) enfocado en bootstrappers tecnicos. Ejecuta el "
    "script y verifica que las carpetas se crearon."
)


def main():
    headers = {"X-Jarvis-Token": TOKEN, "Content-Type": "application/json"}
    payload = {"objective": OBJECTIVE, "priority": 10}
    print(f"POST {API_URL}/execute")
    print(f"objective: {OBJECTIVE[:120]}...")
    try:
        r = requests.post(f"{API_URL}/execute", json=payload, headers=headers,
                           timeout=15)
        print(f"\nstatus: {r.status_code}")
        print(f"response: {r.text[:500]}")
        if r.status_code == 200:
            data = r.json()
            task_id = data.get("task_id")
            print(f"\n[OK] task_id = {task_id}")
            print(f"Para monitorear: curl -H 'X-Jarvis-Token: {TOKEN}' "
                  f"{API_URL}/tasks/{task_id}")
            return 0
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
