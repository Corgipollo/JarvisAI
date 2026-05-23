"""signup_routes.py - Onboarding wizard + landing publica.

Flujo:
  GET  /                    -> landing publica (sin auth)
  GET  /signup              -> wizard HTML (sin auth)
  POST /api/v1/signup       -> crea tenant + redirige a Stripe Checkout
  POST /api/v1/signup/demo  -> dispara un dispatch demo por industria

Sin X-Jarvis-Token en estos endpoints — son publicos. El flujo:
  1. Visitor abre /
  2. Click "Empezar gratis" -> /signup
  3. Llena form: legal_name, contact_email, industry, plan
  4. POST /api/v1/signup -> bootstrap_tenant + Stripe Checkout url
  5. Despues del pago, Stripe redirige a /admin?tenant=X
  6. /api/v1/signup/demo se invoca automaticamente al landing post-Stripe
     para que el cliente vea un primer wow-moment.

Demos por industria:
  ecommerce -> "Analiza mi tienda Shopify y dame 3 mejoras"
  agri_logistics -> "Concilia mis remisiones del mes vs facturas"
  marketing -> "Genera 3 creatives variantes para mi mejor producto"
  dev -> "Audita seguridad de este endpoint FastAPI"
  ...
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, Field

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "http://127.0.0.1:5000")
STATIC = ROOT / "jarvis_v2" / "api" / "static"
INDUSTRIES_VALID = {"ecommerce", "agri_logistics", "marketing", "dev",
                     "video_pipeline", "trading", "generic"}
PLANS_VALID = {"standard", "pro", "enterprise"}

router = APIRouter(tags=["signup"])


class SignupRequest(BaseModel):
    legal_name: str = Field(min_length=2, max_length=100)
    contact_email: str = Field(min_length=5, max_length=120)
    industry: str
    plan: str = "standard"
    tenant_id: str | None = None  # opcional; se genera del legal_name si no


def _slug(text: str) -> str:
    import re
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:32] or "tenant"


@router.post("/api/v1/signup")
def signup(req: SignupRequest):
    """Endpoint publico: crea tenant + devuelve Stripe Checkout URL."""
    if req.industry not in INDUSTRIES_VALID:
        raise HTTPException(400, f"invalid_industry. Valid: {sorted(INDUSTRIES_VALID)}")
    if req.plan not in PLANS_VALID:
        raise HTTPException(400, f"invalid_plan. Valid: {sorted(PLANS_VALID)}")

    tenant_id = req.tenant_id or _slug(req.legal_name)
    # Bootstrap tenant
    from jarvis_v2.core.tenant_context import bootstrap_tenant
    db = bootstrap_tenant(
        tenant_id=tenant_id,
        legal_name=req.legal_name,
        industry=req.industry,
        plan=req.plan,
        contact_email=req.contact_email,
    )

    # Crea Stripe Checkout (demo mode si no hay STRIPE_SECRET_KEY)
    from jarvis_v2.api.stripe_billing import (
        create_checkout_session, CheckoutRequest as CR,
    )
    from jarvis_v2.api.stripe_billing import (
        _stripe_demo_mode, STRIPE_KEY,
    )
    # Re-implementamos sin auth porque create_checkout_session pide token
    if not STRIPE_KEY:
        checkout_url = (f"{PUBLIC_HOST}/admin?checkout=success"
                         f"&tenant={tenant_id}&plan={req.plan}&demo=1")
        return {
            "ok": True,
            "tenant_id": tenant_id,
            "checkout_url": checkout_url,
            "demo_mode": True,
            "db": str(db),
            "next_step": "redirect_to_checkout_url_or_admin",
        }
    # Production: real Stripe
    import stripe
    stripe.api_key = STRIPE_KEY
    from jarvis_v2.api.stripe_billing import PRICE_IDS
    price_id = PRICE_IDS.get(req.plan)
    if not price_id:
        raise HTTPException(500, f"no_price_id_for_plan:{req.plan}")
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=req.contact_email,
            success_url=f"{PUBLIC_HOST}/admin?checkout=success"
                          f"&tenant={tenant_id}&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{PUBLIC_HOST}/signup?checkout=cancel",
            client_reference_id=tenant_id,
            subscription_data={
                "metadata": {"tenant_id": tenant_id, "plan": req.plan},
            },
        )
        return {
            "ok": True, "tenant_id": tenant_id,
            "checkout_url": session.url, "demo_mode": False,
        }
    except Exception as e:
        raise HTTPException(500, f"stripe_error: {e}")


class DemoRequest(BaseModel):
    tenant_id: str
    industry: str


DEMO_OBJECTIVES = {
    "ecommerce": (
        "Analiza una tienda Shopify ejemplo (grop-7604.myshopify.com), "
        "identifica las 3 mejoras de conversion mas importantes y guarda "
        "el reporte en data/tenants/{tid}/artifacts/demo_ecommerce.md"
    ),
    "agri_logistics": (
        "Genera un reporte modelo de conciliacion de remisiones vs "
        "facturas. Output a data/tenants/{tid}/artifacts/demo_agri.md"
    ),
    "marketing": (
        "Genera 3 hooks publicitarios listos para Meta Ads Manager para "
        "un producto generico de e-commerce. Output a "
        "data/tenants/{tid}/artifacts/demo_marketing.md"
    ),
    "dev": (
        "Audita la seguridad de este endpoint FastAPI ejemplo y reporta "
        "las 5 mejoras clave. Output a data/tenants/{tid}/artifacts/demo_dev.md"
    ),
    "video_pipeline": (
        "Disena el pipeline tecnico para narrar 1 capitulo de manhwa "
        "con voz clonada. Output a data/tenants/{tid}/artifacts/demo_video.md"
    ),
    "trading": (
        "Genera un brief de research sobre 3 estrategias forex trending. "
        "Output a data/tenants/{tid}/artifacts/demo_trading.md"
    ),
    "generic": (
        "Lista los 5 procesos automatizables mas comunes en una PyME "
        "mexicana. Output a data/tenants/{tid}/artifacts/demo_generic.md"
    ),
}


@router.post("/api/v1/signup/demo")
def signup_demo_dispatch(req: DemoRequest):
    """Dispara un dispatch demo en la cola para el tenant recien creado.

    No requiere token (esta API es solo callable post-signup desde el
    mismo dominio; pequena fuga vs valor de wow-moment).
    """
    if req.industry not in INDUSTRIES_VALID:
        raise HTTPException(400, "invalid_industry")
    objective_template = DEMO_OBJECTIVES.get(req.industry,
                                                DEMO_OBJECTIVES["generic"])
    objective = objective_template.replace("{tid}", req.tenant_id)
    # Asegurar artifacts dir del tenant
    art_dir = ROOT / "data" / "tenants" / req.tenant_id / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    # Encolar
    from jarvis_v2.task_queue import add
    qid = add(objective, priority=8, source=f"signup_demo:{req.tenant_id}",
              tags=["signup", "demo", req.industry])
    return {"ok": True, "qid": qid, "tenant_id": req.tenant_id,
            "objective_preview": objective[:200]}


# ============================================================================
# HTML estatico
# ============================================================================
@router.get("/")
def landing():
    p = STATIC / "landing.html"
    if not p.exists():
        raise HTTPException(404, "landing.html not built")
    return FileResponse(str(p), media_type="text/html")


@router.get("/signup")
def signup_wizard():
    p = STATIC / "signup.html"
    if not p.exists():
        raise HTTPException(404, "signup.html not built")
    return FileResponse(str(p), media_type="text/html")
