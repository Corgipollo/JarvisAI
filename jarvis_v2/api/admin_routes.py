"""admin_routes.py - Endpoints REST para el Dashboard Admin multi-tenant.

Sirve datos desde data/tenants/{tenant_id}/memory.db (schema multi_tenant.sql).

Endpoints:
    GET  /api/v1/tenants                          -> lista todos los tenants
    GET  /api/v1/tenants/{id}/summary             -> v_tenant_summary row
    GET  /api/v1/tenants/{id}/actions?limit=50    -> action_log reciente
    GET  /api/v1/tenants/{id}/spend?days=30       -> spend_ledger agregado
    GET  /api/v1/tenants/{id}/lessons?limit=20    -> memory_lessons reciente
    GET  /api/v1/tenants/{id}/credentials         -> api_credentials (metadata, sin secrets)
    POST /api/v1/tenants                          -> bootstrap_tenant
    GET  /admin                                   -> sirve admin.html

Autenticacion: por ahora X-Jarvis-Token (el del owner). Multi-user real
viene en sprint enterprise (JWT per-tenant + RBAC).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import os
API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")
TENANTS_ROOT = ROOT / "data" / "tenants"

router = APIRouter(prefix="/api/v1", tags=["admin"])


def _auth(token: str | None) -> None:
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_token")


def _tenant_db(tenant_id: str) -> Path:
    p = TENANTS_ROOT / tenant_id / "memory.db"
    if not p.exists():
        raise HTTPException(status_code=404,
                              detail=f"tenant_not_found:{tenant_id}")
    return p


def _query(db: Path, sql: str, params: tuple = ()) -> list[dict]:
    conn = sqlite3.connect(str(db), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@router.get("/tenants")
def list_tenants(x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    out = []
    if not TENANTS_ROOT.exists():
        return {"tenants": []}
    for tdir in sorted(TENANTS_ROOT.iterdir()):
        db = tdir / "memory.db"
        if not db.exists():
            continue
        try:
            rows = _query(db, "SELECT * FROM v_tenant_summary "
                                 "WHERE tenant_id = ? LIMIT 1",
                            (tdir.name,))
            if rows:
                out.append(rows[0])
        except Exception as e:
            out.append({"tenant_id": tdir.name, "error": str(e)})
    return {"tenants": out, "count": len(out)}


@router.get("/tenants/{tenant_id}/summary")
def tenant_summary(tenant_id: str,
                    x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    db = _tenant_db(tenant_id)
    rows = _query(db, "SELECT * FROM v_tenant_summary WHERE tenant_id = ?",
                  (tenant_id,))
    if not rows:
        raise HTTPException(404, "tenant_not_found")
    return rows[0]


@router.get("/tenants/{tenant_id}/actions")
def tenant_actions(tenant_id: str, limit: int = Query(50, le=500),
                    x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    db = _tenant_db(tenant_id)
    rows = _query(
        db,
        "SELECT id, ts, action_type, objective_summary, target_or_command, "
        "cost_usd, success, elapsed_ms, error, initiated_by "
        "FROM action_log WHERE tenant_id = ? ORDER BY id DESC LIMIT ?",
        (tenant_id, limit),
    )
    return {"actions": rows, "count": len(rows)}


@router.get("/tenants/{tenant_id}/spend")
def tenant_spend(tenant_id: str, days: int = Query(30, le=365),
                  x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    db = _tenant_db(tenant_id)
    rows_total = _query(
        db,
        "SELECT provider, model, "
        "COUNT(*) AS calls, "
        "SUM(tokens_in) AS tokens_in, "
        "SUM(tokens_out) AS tokens_out, "
        "ROUND(SUM(cost_usd), 4) AS cost_usd "
        "FROM spend_ledger WHERE tenant_id = ? "
        "AND ts > datetime('now', ?) "
        "GROUP BY provider, model ORDER BY calls DESC",
        (tenant_id, f"-{days} days"),
    )
    rows_daily = _query(
        db,
        "SELECT DATE(ts) AS day, "
        "ROUND(SUM(cost_usd), 4) AS cost_usd, "
        "SUM(tokens_in + tokens_out) AS tokens "
        "FROM spend_ledger WHERE tenant_id = ? "
        "AND ts > datetime('now', ?) "
        "GROUP BY DATE(ts) ORDER BY day ASC",
        (tenant_id, f"-{days} days"),
    )
    return {"days": days, "by_provider": rows_total, "daily": rows_daily}


@router.get("/tenants/{tenant_id}/lessons")
def tenant_lessons(tenant_id: str, limit: int = Query(20, le=200),
                    x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    db = _tenant_db(tenant_id)
    rows = _query(
        db,
        "SELECT id, ts, industry, insight, tags, severity, confidence, "
        "helpful_count FROM memory_lessons WHERE tenant_id = ? "
        "ORDER BY id DESC LIMIT ?".replace("ts", "created_at"),
        (tenant_id, limit),
    )
    return {"lessons": rows, "count": len(rows)}


@router.get("/tenants/{tenant_id}/credentials")
def tenant_credentials(tenant_id: str,
                        x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    db = _tenant_db(tenant_id)
    rows = _query(
        db,
        "SELECT provider, handle, scopes, created_at, last_used, "
        "rotated_at, expires_at, is_active "
        "FROM api_credentials WHERE tenant_id = ? ORDER BY provider",
        (tenant_id,),
    )
    return {"credentials": rows, "count": len(rows),
            "note": "secret_ref omitido — vive cifrado en secrets.enc"}


class BootstrapRequest(BaseModel):
    tenant_id: str
    legal_name: str
    industry: str = "generic"
    plan: str = "standard"
    contact_email: str | None = None


@router.post("/tenants")
def bootstrap(req: BootstrapRequest,
              x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    from jarvis_v2.core.tenant_context import bootstrap_tenant
    db = bootstrap_tenant(
        tenant_id=req.tenant_id,
        legal_name=req.legal_name,
        industry=req.industry,
        plan=req.plan,
        contact_email=req.contact_email,
    )
    return {"ok": True, "tenant_id": req.tenant_id, "db": str(db)}


class DebateRequest(BaseModel):
    content: str
    focus: str = "general security + correctness"
    max_rounds: int = 2
    auto: bool = True  # solo dispara debate si hay keywords de riesgo


@router.post("/debate")
def debate_endpoint(req: DebateRequest,
                     x_jarvis_token: str | None = Header(default=None)):
    """Somete codigo o diseno al tribunal interno (proposer-critic).

    Si auto=True (default), solo debate si detect keywords de riesgo
    (sql, webhook, stripe, auth, etc). Sino approved instantaneo.
    """
    _auth(x_jarvis_token)
    from jarvis_v2.core.debate_engine import (
        debate, debate_if_risky, should_trigger_debate,
    )
    if req.auto:
        return debate_if_risky(req.content, focus_hint=req.focus,
                                max_rounds=req.max_rounds)
    return debate(req.content, focus_areas=req.focus,
                   max_rounds=req.max_rounds)


# Admin HTML (static)
ADMIN_HTML = ROOT / "jarvis_v2" / "api" / "static" / "admin.html"


def serve_admin():
    if not ADMIN_HTML.exists():
        raise HTTPException(404, "admin.html not built")
    return FileResponse(str(ADMIN_HTML), media_type="text/html")
