"""update_dns.py - DuckDNS auto-update IP.

Mantiene jarvis-emmanuel.duckdns.org sincronizado con la IP publica
actual. Corre cada 5 min via schtask Jarvis_DuckDNS.

REQUISITOS HUMANOS (UNA vez, 30 segundos):
  1. Abrir https://www.duckdns.org/
  2. Login con Twitter/GitHub/Reddit/Google (eliges el que ya uses)
  3. Crear subdomain (sugerencia: 'jarvis-emmanuel')
  4. Copiar el token de la pagina (UUID formato xxxx-xxxx-xxxx)
  5. setx DUCKDNS_TOKEN "tu-uuid-aqui"
  6. setx DUCKDNS_SUBDOMAIN "jarvis-emmanuel"
  7. Reiniciar PowerShell o ejecutar este script con env vars en sesion

Despues: la URL https://jarvis-emmanuel.duckdns.org apunta a tu IP
publica de forma permanente. Sin captcha, sin tarjeta, sin caducidad.

NOTA: DuckDNS no provee SSL nativo. Para HTTPS valido vas a necesitar:
  - Combinarlo con Cloudflare gratis (proxy DNS frente al duckdns) O
  - Cloudflare Tunnel hacia tu dominio duckdns (cloudflared route dns)
"""
from __future__ import annotations

import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]

TOKEN = os.environ.get("DUCKDNS_TOKEN", "")
SUBDOMAIN = os.environ.get("DUCKDNS_SUBDOMAIN", "jarvis-emmanuel")
LOG = ROOT / "data" / "duckdns.log"
URL_FILE = ROOT / "data" / "public_url.txt"


def _log(msg: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_public_ip() -> str | None:
    """Pide IP publica a 3 servicios en cascada. Robusto si uno cae."""
    services = [
        "https://api.ipify.org",
        "https://icanhazip.com",
        "https://ifconfig.me/ip",
    ]
    for url in services:
        try:
            with httpx.Client(timeout=10) as cli:
                r = cli.get(url)
            if r.status_code == 200:
                ip = r.text.strip()
                # validacion basica
                socket.inet_aton(ip)
                return ip
        except Exception as e:
            _log(f"ip svc {url} fail: {e}")
            continue
    return None


def duckdns_update(token: str, subdomain: str, ip: str) -> dict:
    """Llama API DuckDNS para actualizar A record."""
    url = (f"https://www.duckdns.org/update?"
           f"domains={subdomain}&token={token}&ip={ip}")
    try:
        with httpx.Client(timeout=15) as cli:
            r = cli.get(url)
        text = r.text.strip()
        return {"ok": text == "OK", "response": text,
                "status": r.status_code}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    if not TOKEN:
        _log("ERROR: DUCKDNS_TOKEN not set. Skipping update.")
        _log("Setup (30 sec, UNA vez):")
        _log("  1. Abre https://www.duckdns.org/ y login con Twitter/GitHub/Google")
        _log("  2. Crea subdomain jarvis-emmanuel (o el que quieras)")
        _log("  3. Copia el token UUID")
        _log("  4. PowerShell: setx DUCKDNS_TOKEN \"<uuid>\"")
        _log("  5. setx DUCKDNS_SUBDOMAIN \"jarvis-emmanuel\"")
        sys.exit(1)

    ip = get_public_ip()
    if not ip:
        _log("FATAL: no se pudo obtener IP publica")
        sys.exit(2)

    _log(f"IP publica: {ip}, subdomain: {SUBDOMAIN}")
    result = duckdns_update(TOKEN, SUBDOMAIN, ip)
    if result.get("ok"):
        _log(f"UPDATE OK: {SUBDOMAIN}.duckdns.org -> {ip}")
        # Persistir URL canonica
        URL_FILE.write_text(f"https://{SUBDOMAIN}.duckdns.org",
                             encoding="utf-8")
        # Tambien deja el cname duckdns como nota
        print(f"public_url updated: https://{SUBDOMAIN}.duckdns.org")
    else:
        _log(f"UPDATE FAIL: {result}")
        sys.exit(3)


if __name__ == "__main__":
    main()
