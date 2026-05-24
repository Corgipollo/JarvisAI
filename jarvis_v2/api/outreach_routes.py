"""outreach_routes.py - CRM minimo + cold email tool + open/click tracking.

Sin services externos (no SendGrid, no Mailchimp). Usa SMTP del propio
Gmail/Outlook de Emmanuel via app password. Tracking via:
  - 1x1 pixel transparente -> GET /track/open/{lead_id}
  - URL del email apunta a /track/click/{lead_id}?to=<destino> -> 302 redirect

CRM schema vive en data/tenants/default/memory.db tabla 'outreach_leads'.
NO multi-tenant (es la lista de prospects de Emmanuel, no de sus clientes).

Endpoints:
  GET    /api/v1/outreach/leads             tabla con stats por lead
  POST   /api/v1/outreach/leads/import      bulk import inicial
  POST   /api/v1/outreach/send              {lead_ids[], template_id} -> envia
  GET    /api/v1/outreach/templates         lista templates
  GET    /api/v1/outreach/stats             campaign stats agregada
  GET    /track/open/{lead_id}.png          pixel tracking (no auth)
  GET    /track/click/{lead_id}             302 redirect + count click

SMTP config via env vars:
  SMTP_HOST=smtp.gmail.com
  SMTP_PORT=587
  SMTP_USER=tu@gmail.com
  SMTP_PASS=app_password_16_chars  (NO la password real - app password de Gmail)
  SMTP_FROM_NAME=Emmanuel Pedraza
"""
from __future__ import annotations

import os
import smtplib
import sqlite3
import sys
import uuid
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")
DEFAULT_TENANT_DB = ROOT / "data" / "tenants" / "default" / "memory.db"
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Emmanuel Pedraza")

router = APIRouter(tags=["outreach"])


def _auth(token: str | None) -> None:
    if token != API_TOKEN:
        raise HTTPException(401, "invalid_token")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DEFAULT_TENANT_DB), timeout=10)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS outreach_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            vertical TEXT,
            location TEXT,
            attack_angle TEXT,
            contact_name TEXT,
            contact_email TEXT,
            contact_title TEXT DEFAULT 'COO',
            icp_segment TEXT,
            status TEXT DEFAULT 'queued',
            opens INTEGER DEFAULT 0,
            clicks INTEGER DEFAULT 0,
            replied INTEGER DEFAULT 0,
            last_sent_at TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_leads_status ON outreach_leads(status);
        CREATE INDEX IF NOT EXISTS idx_leads_icp ON outreach_leads(icp_segment);

        CREATE TABLE IF NOT EXISTS outreach_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            event TEXT,
            ts TEXT DEFAULT (datetime('now')),
            ip TEXT,
            user_agent TEXT,
            metadata TEXT,
            FOREIGN KEY (lead_id) REFERENCES outreach_leads(id)
        );
        CREATE INDEX IF NOT EXISTS idx_events_lead ON outreach_events(lead_id);
    """)
    conn.commit()


class LeadImport(BaseModel):
    company: str
    vertical: str
    location: str = ""
    attack_angle: str = ""
    contact_name: str = ""
    contact_email: str = ""
    contact_title: str = "COO"
    icp_segment: str = "generic"


class BulkImport(BaseModel):
    leads: list[LeadImport]


@router.post("/api/v1/outreach/leads/import")
def import_leads(req: BulkImport, x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    conn = _connect()
    n = 0
    for lead in req.leads:
        cur = conn.execute(
            "SELECT id FROM outreach_leads WHERE company = ?",
            (lead.company,),
        )
        if cur.fetchone():
            continue  # ya existe, no duplicar
        conn.execute(
            "INSERT INTO outreach_leads(company, vertical, location, "
            "attack_angle, contact_name, contact_email, contact_title, "
            "icp_segment) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (lead.company, lead.vertical, lead.location, lead.attack_angle,
             lead.contact_name, lead.contact_email, lead.contact_title,
             lead.icp_segment),
        )
        n += 1
    conn.commit()
    conn.close()
    return {"ok": True, "inserted": n, "total_requested": len(req.leads)}


@router.get("/api/v1/outreach/leads")
def list_leads(x_jarvis_token: str | None = Header(default=None),
                limit: int = 200, icp: str | None = None,
                status: str | None = None):
    _auth(x_jarvis_token)
    conn = _connect()
    sql = "SELECT * FROM outreach_leads WHERE 1=1"
    params: list[Any] = []
    if icp:
        sql += " AND icp_segment = ?"
        params.append(icp)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id ASC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return {"leads": rows, "count": len(rows)}


@router.get("/api/v1/outreach/stats")
def stats(x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    conn = _connect()
    summary = conn.execute("""
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) AS sent,
          SUM(CASE WHEN status='queued' THEN 1 ELSE 0 END) AS queued,
          SUM(CASE WHEN status='replied' THEN 1 ELSE 0 END) AS replied,
          SUM(opens) AS total_opens,
          SUM(clicks) AS total_clicks
        FROM outreach_leads
    """).fetchone()
    by_icp = [dict(r) for r in conn.execute("""
        SELECT icp_segment AS icp, COUNT(*) AS n,
               SUM(opens) AS opens, SUM(clicks) AS clicks,
               SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) AS sent
        FROM outreach_leads GROUP BY icp_segment
    """).fetchall()]
    conn.close()
    return {"summary": dict(summary) if summary else {}, "by_icp": by_icp}


# ============================================================================
# Templates de email
# ============================================================================
TEMPLATES: dict[str, dict] = {
    "agro_v1": {
        "subject": "Su equipo pierde 4 horas los lunes cruzando remisiones",
        "body_text": (
            "Hola {contact_name},\n\n"
            "Vi la operacion de fletes y acopio que manejan en {company}. "
            "Cuadrar toneladas de la bascula con humedad y la carta porte "
            "en el ERP es un cuello de botella que se hace a mano.\n\n"
            "Grabe un video de 60 segundos mostrando como Jarvis V2 lee los "
            "tickets en pantalla y concilia 157 remisiones en 47 segundos, "
            "sin integraciones complejas:\n\n"
            "{tracked_url}\n\n"
            "Sin tarjeta. Solo verlo operar. Si les ahorra tiempo, respondan.\n\n"
            "Emmanuel\n{public_host}"
        ),
    },
    "ecommerce_v1": {
        "subject": "Pausar ROAS cae a tiempo: lo veo desde mi GPU",
        "body_text": (
            "Hola {contact_name},\n\n"
            "{company} maneja catalogo de e-commerce con margenes que se "
            "queman cuando una campana de Meta Ads sigue corriendo despues "
            "de que el ROAS cayo del threshold.\n\n"
            "60 segundos mostrando Jarvis monitoreando ROAS + pausando ads "
            "y subiendo imagenes a Shopify:\n\n"
            "{tracked_url}\n\n"
            "Sin tarjeta. 14 dias gratis.\n\n"
            "Emmanuel\n{public_host}"
        ),
    },
    "agency_v1": {
        "subject": "Reportes ROAS automaticos para sus 30 cuentas",
        "body_text": (
            "Hola {contact_name},\n\n"
            "Si {company} manda reportes manuales de campanas Meta/Google a "
            "30+ cuentas todos los lunes, Jarvis V2 los genera leyendo Ads "
            "Manager y rellenando Google Sheets en lote.\n\n"
            "60 segundos viendolo trabajar:\n\n"
            "{tracked_url}\n\n"
            "Cero curva. Setup en 30 segundos.\n\n"
            "Emmanuel\n{public_host}"
        ),
    },
}


@router.get("/api/v1/outreach/templates")
def list_templates(x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    return {
        "templates": [
            {"id": tid, "subject": t["subject"],
             "body_preview": t["body_text"][:200]}
            for tid, t in TEMPLATES.items()
        ]
    }


class SendRequest(BaseModel):
    lead_ids: list[int]
    template_id: str = "agro_v1"
    dry_run: bool = False  # si True, NO envia, solo previsualiza


@router.post("/api/v1/outreach/send")
def send_emails(req: SendRequest, request: Request,
                 x_jarvis_token: str | None = Header(default=None)):
    """Envia template a lista de leads. Cada email lleva pixel de tracking
    + link tracked. Si dry_run=True, solo previsualiza sin SMTP."""
    _auth(x_jarvis_token)
    if req.template_id not in TEMPLATES:
        raise HTTPException(400, f"unknown_template:{req.template_id}")
    tpl = TEMPLATES[req.template_id]

    public_host = (request.headers.get("x-forwarded-host")
                   or request.headers.get("host")
                   or "127.0.0.1:5000")
    proto = request.headers.get("x-forwarded-proto", "https")
    base = f"{proto}://{public_host}"

    if not req.dry_run:
        if not (SMTP_USER and SMTP_PASS):
            raise HTTPException(500,
                "SMTP not configured. Set SMTP_USER + SMTP_PASS env vars first")

    conn = _connect()
    results = []
    smtp = None
    try:
        if not req.dry_run:
            smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)

        for lead_id in req.lead_ids:
            row = conn.execute(
                "SELECT * FROM outreach_leads WHERE id = ?",
                (lead_id,)).fetchone()
            if not row or not row["contact_email"]:
                results.append({"lead_id": lead_id, "ok": False,
                                 "error": "no_email"})
                continue

            tracked_url = f"{base}/track/click/{lead_id}?to=/"
            pixel = (f'<img src="{base}/track/open/{lead_id}.png" '
                     f'width="1" height="1" alt="" />')

            body_text = tpl["body_text"].format(
                contact_name=row["contact_name"] or "equipo",
                company=row["company"],
                tracked_url=tracked_url,
                public_host=base,
            )
            body_html = ("<html><body><pre style='font-family:sans-serif'>"
                          + body_text + "</pre>" + pixel + "</body></html>")

            if req.dry_run:
                results.append({
                    "lead_id": lead_id, "ok": True, "dry_run": True,
                    "to": row["contact_email"],
                    "subject": tpl["subject"],
                    "body_preview": body_text[:300],
                })
                continue

            msg = MIMEMultipart("alternative")
            msg["Subject"] = tpl["subject"]
            msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
            msg["To"] = row["contact_email"]
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            try:
                smtp.send_message(msg)
                conn.execute(
                    "UPDATE outreach_leads SET status='sent', "
                    "last_sent_at = datetime('now') WHERE id = ?",
                    (lead_id,))
                conn.execute(
                    "INSERT INTO outreach_events(lead_id, event, metadata) "
                    "VALUES (?, 'sent', ?)",
                    (lead_id, req.template_id))
                results.append({"lead_id": lead_id, "ok": True})
            except Exception as e:
                results.append({"lead_id": lead_id, "ok": False,
                                 "error": str(e)[:200]})
        conn.commit()
    finally:
        if smtp:
            try:
                smtp.quit()
            except Exception:
                pass
        conn.close()

    return {"ok": True, "results": results, "dry_run": req.dry_run}


# ============================================================================
# Tracking endpoints (sin auth - los abre el cliente desde su mail client)
# ============================================================================
ONE_PX_PNG = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
    0x89, 0x00, 0x00, 0x00, 0x0D, 0x49, 0x44, 0x41,
    0x54, 0x78, 0x9C, 0x62, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
    0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,
    0x42, 0x60, 0x82,
])


@router.get("/track/open/{lead_id}.png")
def track_open(lead_id: int, request: Request):
    """Pixel 1x1 transparente. Incrementa opens del lead."""
    try:
        conn = _connect()
        conn.execute(
            "UPDATE outreach_leads SET opens = opens + 1 WHERE id = ?",
            (lead_id,))
        conn.execute(
            "INSERT INTO outreach_events(lead_id, event, ip, user_agent) "
            "VALUES (?, 'open', ?, ?)",
            (lead_id, request.client.host if request.client else "?",
             request.headers.get("user-agent", "")[:200]))
        conn.commit()
        conn.close()
    except Exception:
        pass  # no rompamos el pixel si DB falla
    return Response(content=ONE_PX_PNG, media_type="image/png",
                     headers={"Cache-Control": "no-cache, no-store"})


@router.get("/track/click/{lead_id}")
def track_click(lead_id: int, request: Request, to: str = "/"):
    """Cuenta click y redirect al destino. 'to' es path relativo o URL absoluta."""
    try:
        conn = _connect()
        conn.execute(
            "UPDATE outreach_leads SET clicks = clicks + 1 WHERE id = ?",
            (lead_id,))
        conn.execute(
            "INSERT INTO outreach_events(lead_id, event, ip, user_agent, metadata) "
            "VALUES (?, 'click', ?, ?, ?)",
            (lead_id, request.client.host if request.client else "?",
             request.headers.get("user-agent", "")[:200], to[:200]))
        conn.commit()
        conn.close()
    except Exception:
        pass

    # Si 'to' es absoluto, redirect ahi. Si es relativo, prepende public host.
    if to.startswith("http"):
        target = to
    else:
        public_host = (request.headers.get("x-forwarded-host")
                       or request.headers.get("host")
                       or "127.0.0.1:5000")
        proto = request.headers.get("x-forwarded-proto", "https")
        target = f"{proto}://{public_host}{to if to.startswith('/') else '/' + to}"
    return RedirectResponse(url=target, status_code=302)
