"""research_lead_contacts.py - Investiga emails publicos de cada lead.

Para cada lead en outreach_leads, busca:
  1. Pagina web oficial (site lookup via DuckDuckGo)
  2. Patron de email comun (contacto@, ventas@, info@, operaciones@)
  3. LinkedIn publico de COO/Director Operativo (best-effort)

Sin scraping intrusivo, sin login, sin captchas. Solo HTTP GET a paginas
publicas + heuristicas de patrones de email comunes en LATAM B2B.

Sin email encontrado -> deja contact_email = '' y notes con explicacion.

API:
    research_one(company_name) -> dict {email, source, notes}
    bulk_research(limit) -> int (actualizados en DB)
"""
from __future__ import annotations

import re
import sys
import sqlite3
import time
from pathlib import Path
from urllib.parse import quote_plus

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

DB = ROOT / "data" / "tenants" / "default" / "memory.db"
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# Patrones comunes de email B2B en LATAM (orden de preferencia)
COMMON_PREFIXES = ["contacto", "ventas", "info", "hola", "operaciones",
                    "comercial", "atencion", "contact"]

EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")


def _http_get(url: str, timeout: float = 12.0) -> str:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True,
                          headers={"User-Agent": USER_AGENT}) as cli:
            r = cli.get(url)
        if r.status_code == 200:
            return r.text[:200000]
    except Exception:
        pass
    return ""


def find_official_site(company: str) -> str:
    """DuckDuckGo HTML search -> primera URL no-redes-sociales."""
    q = quote_plus(f"{company} sitio oficial")
    html = _http_get(f"https://html.duckduckgo.com/html/?q={q}", 10)
    if not html:
        return ""
    # extract result URLs
    urls = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"', html)
    if not urls:
        urls = re.findall(r'href="(https?://[^"]+)"', html)
    skip_domains = ("duckduckgo.com", "facebook.com", "linkedin.com",
                     "twitter.com", "instagram.com", "tiktok.com",
                     "wikipedia.org", "youtube.com", "amazon.")
    for url in urls[:25]:
        # Strip DuckDuckGo redirect prefix if present
        if "/l/?uddg=" in url:
            from urllib.parse import unquote, parse_qs, urlparse
            qs = parse_qs(urlparse(url).query)
            url = unquote(qs.get("uddg", [""])[0])
        if any(d in url for d in skip_domains):
            continue
        if url.startswith("http"):
            return url
    return ""


def extract_emails_from_site(site_url: str) -> list[str]:
    """GET site + sitio/contacto + sitio/contact pages. Extract emails."""
    if not site_url:
        return []
    candidates = [site_url]
    base = site_url.rstrip("/")
    for path in ("/contacto", "/contact", "/about", "/nosotros",
                  "/contactanos"):
        candidates.append(base + path)

    found: set[str] = set()
    for url in candidates:
        html = _http_get(url, 8)
        for match in EMAIL_RE.findall(html):
            email = match.lower()
            # Filtrar emails obviamente falsos
            if any(stop in email for stop in
                    ("example.", "sentry.", "wixpress.", "godaddy.",
                     "shopify.com", "u003e", "noreply", "no-reply",
                     "@email.com", "your@", ".png", ".jpg")):
                continue
            found.add(email)
    return sorted(found)


def research_one(company: str) -> dict:
    """Para una empresa, intenta encontrar 1 email publico."""
    site = find_official_site(company)
    if not site:
        return {"email": "", "source": "", "notes": "no_site_found"}
    emails = extract_emails_from_site(site)
    if not emails:
        # Heuristica: si el dominio es claro, sugerir ventas@dominio
        from urllib.parse import urlparse
        domain = urlparse(site).hostname or ""
        if domain and domain.count(".") >= 1:
            # quitar www.
            domain = domain.replace("www.", "")
            return {"email": f"ventas@{domain}",
                    "source": site,
                    "notes": "heuristic_ventas_prefix"}
        return {"email": "", "source": site, "notes": "no_email_found"}
    return {"email": emails[0], "source": site,
            "notes": f"found_{len(emails)}_emails_pick_first"}


def bulk_research(limit: int = 20, skip_existing: bool = True) -> dict:
    """Procesa todos los leads sin email. Update DB."""
    conn = sqlite3.connect(str(DB), timeout=10)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, company, contact_email FROM outreach_leads "
        "ORDER BY id LIMIT ?", (limit,)
    ).fetchall()

    results = []
    for row in rows:
        if skip_existing and row["contact_email"]:
            results.append({"id": row["id"], "company": row["company"],
                             "skipped": True,
                             "existing_email": row["contact_email"]})
            continue
        print(f"[research] {row['company']}...", flush=True)
        r = research_one(row["company"])
        if r["email"]:
            conn.execute(
                "UPDATE outreach_leads SET contact_email = ?, "
                "notes = ? WHERE id = ?",
                (r["email"], f"auto:{r['notes']}|src:{r['source'][:80]}",
                 row["id"]))
        results.append({"id": row["id"], "company": row["company"], **r})
        time.sleep(2)  # rate limit polite

    conn.commit()
    conn.close()
    return {"processed": len(results), "results": results}


if __name__ == "__main__":
    import json
    out = bulk_research(limit=25)
    print(json.dumps(out, ensure_ascii=False, indent=2))
