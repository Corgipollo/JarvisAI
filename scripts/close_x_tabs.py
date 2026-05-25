"""close_x_tabs.py - Cierra todas las pestanas X.com / Twitter en Brave CDP."""
import requests
import sys

CDP = "http://127.0.0.1:9222"
try:
    tabs = requests.get(f"{CDP}/json/list", timeout=5).json()
except Exception as e:
    print(f"CDP no responde: {e}")
    sys.exit(1)

bad = [t for t in tabs if any(host in t.get("url", "").lower()
        for host in ["x.com", "twitter.com"])]
print(f"Encontradas {len(bad)} pestanas X/Twitter de {len(tabs)} totales")

closed = 0
for t in bad:
    tid = t.get("id")
    try:
        requests.get(f"{CDP}/json/close/{tid}", timeout=3)
        closed += 1
        print(f"  closed: {t.get('url', '')[:80]}")
    except Exception as e:
        print(f"  fail {tid}: {e}")

print(f"Total cerradas: {closed}/{len(bad)}")
