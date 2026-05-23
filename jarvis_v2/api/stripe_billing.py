"""stripe_billing.py - Endpoints Stripe + webhook + plan billing per-tenant.

Modelo de billing (Jarvis V2 SaaS):
  Standard   $1499/mes MXN (~$80 USD) — 1 vertical, 50 actions/dia, 2 integraciones
  Pro        $4999/mes MXN (~$270 USD) — 300 actions/dia, 10 integraciones
  Enterprise $14999/mes MXN (~$810 USD) — illimited, SLA 99.9%

Flow:
  1. Cliente abre /admin -> Settings -> Suscribirse
  2. POST /api/v1/billing/checkout-session crea Stripe Checkout
  3. Cliente paga en hosted Stripe page
  4. Stripe webhook -> POST /api/v1/billing/webhook
  5. Updateamos data/tenants/{id}/memory.db tenant_meta.plan + stripe_*

DEMO MODE: si STRIPE_SECRET_KEY no esta set, los endpoints devuelven
respuestas mockeadas sensatas para que el dashboard se vea funcional sin
configuracion real. En produccion: set las env vars y descomenta el import
real de stripe.

Required env vars (production):
  STRIPE_SECRET_KEY=sk_test_... o sk_live_...
  STRIPE_PUBLISHABLE_KEY=pk_test_... o pk_live_...
  STRIPE_WEBHOOK_SECRET=whsec_...
  STRIPE_PRICE_STANDARD=price_xxx
  STRIPE_PRICE_PRO=price_xxx
  STRIPE_PRICE_ENTERPRISE=price_xxx
  PUBLIC_HOST=https://yourdomain.com  # para success_url/cancel_url
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

# Hardening tras dogfooding audit 2026-05-23:
#   - Validacion estricta de tenant_id (path traversal + SQL injection indirecta)
#   - Bloqueo de demo_mode en webhook cuando STRIPE_SECRET_KEY esta set
#   - Idempotency table para evitar doble-procesado de event.id
#   - BEGIN TRANSACTION en webhook update
TENANT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

API_TOKEN = os.environ.get("JARVIS_API_TOKEN", "jarvis_a8x29kfp3lz7m2qw9bdv")
STRIPE_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUB = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WH_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "http://127.0.0.1:5000")

PRICE_IDS = {
    "standard": os.environ.get("STRIPE_PRICE_STANDARD", ""),
    "pro": os.environ.get("STRIPE_PRICE_PRO", ""),
    "enterprise": os.environ.get("STRIPE_PRICE_ENTERPRISE", ""),
}

PLAN_LIMITS = {
    "standard": {"actions_per_day": 50, "integrations": 2,
                  "memory_days": 30, "price_mxn": 1499, "price_usd": 80},
    "pro": {"actions_per_day": 300, "integrations": 10,
             "memory_days": 365, "price_mxn": 4999, "price_usd": 270},
    "enterprise": {"actions_per_day": None, "integrations": None,
                    "memory_days": None, "price_mxn": 14999, "price_usd": 810},
}

TENANTS_ROOT = ROOT / "data" / "tenants"
router = APIRouter(prefix="/api/v1/billing", tags=["billing"])


def _auth(token: str | None) -> None:
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_token")


def _validate_tenant_id(tenant_id: str | None) -> str:
    """GUARDRAIL: rechaza tenant_id con path traversal o caracteres invalidos.
    Issue #4/#8 del audit: prevenir '../../' o '1 OR 1=1'."""
    if not tenant_id or not isinstance(tenant_id, str):
        raise HTTPException(400, "invalid_tenant_id_empty")
    if not TENANT_ID_RE.match(tenant_id):
        raise HTTPException(400,
            f"invalid_tenant_id_format:{tenant_id[:32]} (allowed: [a-z0-9_-], len 2-41, no path chars)")
    return tenant_id


def _tenant_db(tenant_id: str) -> Path:
    tenant_id = _validate_tenant_id(tenant_id)
    p = TENANTS_ROOT / tenant_id / "memory.db"
    if not p.exists():
        raise HTTPException(404, f"tenant_not_found:{tenant_id}")
    return p


def _ensure_stripe_cols(db: Path) -> None:
    """ALTER TABLE para agregar columnas Stripe a tenant_meta si faltan."""
    conn = sqlite3.connect(str(db), timeout=5)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(tenant_meta)")}
        for col in ("stripe_customer_id", "stripe_subscription_id",
                     "stripe_subscription_status", "current_period_end"):
            if col not in cols:
                conn.execute(f"ALTER TABLE tenant_meta ADD COLUMN {col} TEXT")
        conn.commit()
    finally:
        conn.close()


def _stripe_demo_mode() -> bool:
    return not STRIPE_KEY


# ============================================================================
# Endpoints públicos del UI
# ============================================================================
@router.get("/plans")
def list_plans(x_jarvis_token: str | None = Header(default=None)):
    _auth(x_jarvis_token)
    return {
        "plans": [
            {"slug": slug, **limits, "stripe_price_id": PRICE_IDS.get(slug, "")}
            for slug, limits in PLAN_LIMITS.items()
        ],
        "demo_mode": _stripe_demo_mode(),
        "publishable_key": STRIPE_PUB,
    }


class CheckoutRequest(BaseModel):
    tenant_id: str
    plan: str  # standard | pro | enterprise
    success_path: str = "/admin?checkout=success"
    cancel_path: str = "/admin?checkout=cancel"


@router.post("/checkout-session")
def create_checkout_session(req: CheckoutRequest,
                              x_jarvis_token: str | None = Header(default=None)):
    """Crea Stripe Checkout Session. Cliente es redirigido a hosted page."""
    _auth(x_jarvis_token)
    if req.plan not in PLAN_LIMITS:
        raise HTTPException(400, f"invalid_plan:{req.plan}")
    db = _tenant_db(req.tenant_id)
    _ensure_stripe_cols(db)

    if _stripe_demo_mode():
        return {
            "demo_mode": True,
            "url": f"{PUBLIC_HOST}{req.success_path}&tenant={req.tenant_id}"
                    f"&plan={req.plan}&demo=1",
            "session_id": f"cs_demo_{int(time.time())}",
            "note": "STRIPE_SECRET_KEY not set. In production: real Checkout.",
        }

    # Producción: crear sesion real
    try:
        import stripe
        stripe.api_key = STRIPE_KEY
        price_id = PRICE_IDS.get(req.plan)
        if not price_id:
            raise HTTPException(500, f"no_price_id_for_plan:{req.plan}")

        # Buscar customer existente
        conn = sqlite3.connect(str(db), timeout=5)
        cur = conn.execute(
            "SELECT stripe_customer_id, contact_email FROM tenant_meta "
            "WHERE tenant_id = ?", (req.tenant_id,))
        row = cur.fetchone()
        conn.close()
        customer_id = row[0] if row else None
        email = row[1] if row else None

        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer=customer_id,
            customer_email=email if not customer_id else None,
            success_url=f"{PUBLIC_HOST}{req.success_path}"
                          "&session_id={CHECKOUT_SESSION_ID}",
            cancel_url=f"{PUBLIC_HOST}{req.cancel_path}",
            client_reference_id=req.tenant_id,
            subscription_data={
                "metadata": {"tenant_id": req.tenant_id, "plan": req.plan},
            },
        )
        return {"url": session.url, "session_id": session.id,
                "demo_mode": False}
    except ImportError:
        raise HTTPException(500,
            "stripe package not installed. pip install stripe")
    except Exception as e:
        raise HTTPException(500, f"stripe_error: {e}")


@router.get("/subscription/{tenant_id}")
def get_subscription(tenant_id: str,
                      x_jarvis_token: str | None = Header(default=None)):
    """Status actual de la suscripcion del tenant + limits."""
    _auth(x_jarvis_token)
    db = _tenant_db(tenant_id)
    _ensure_stripe_cols(db)
    conn = sqlite3.connect(str(db), timeout=5)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT tenant_id, plan, stripe_customer_id, stripe_subscription_id, "
        "stripe_subscription_status, current_period_end "
        "FROM tenant_meta WHERE tenant_id = ?", (tenant_id,)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "tenant_not_found")
    plan = row["plan"] or "standard"
    return {
        "tenant_id": row["tenant_id"],
        "plan": plan,
        "limits": PLAN_LIMITS.get(plan, {}),
        "stripe_customer_id": row["stripe_customer_id"],
        "stripe_subscription_id": row["stripe_subscription_id"],
        "stripe_subscription_status": row["stripe_subscription_status"],
        "current_period_end": row["current_period_end"],
        "demo_mode": _stripe_demo_mode(),
    }


# ============================================================================
# Webhook receiver (Stripe -> jarvis)
# ============================================================================
def _ensure_idempotency_table(db: Path) -> None:
    """Issue #2 audit: tabla de event_id procesados para evitar doble-update."""
    conn = sqlite3.connect(str(db), timeout=5)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stripe_events_processed (
                event_id TEXT PRIMARY KEY,
                event_type TEXT,
                processed_at TEXT DEFAULT (datetime('now')),
                tenant_id TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


SUPPORTED_EVENT_TYPES = {
    "checkout.session.completed",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "invoice.payment_failed",  # issue #6: handler explicito
    "invoice.payment_succeeded",
}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Recibe events de Stripe: subscription created/updated/canceled.

    HARDENING tras dogfooding audit (5 issues CRITICAL+HIGH resueltos):
      #1 CRITICAL: demo_mode SOLO si STRIPE_SECRET_KEY ausente. Si esta set
         pero WH_SECRET falta -> 500, NO acepta JSON sin firma.
      #2 CRITICAL: idempotency via stripe_events_processed table.
      #3 HIGH:    leak minimizado en response (no eco de stripe_customer_id).
      #4 HIGH:    tenant_id validado con TENANT_ID_RE (path traversal block).
      #5 HIGH:    BEGIN TRANSACTION explicita + commit atomic.

    NO requiere X-Jarvis-Token (lo firma Stripe via stripe-signature header).
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    client_ip = request.client.host if request.client else "?"

    # Issue #1 + #7 CRITICAL/MEDIUM: rechazar inseguridad en produccion
    if STRIPE_KEY and not STRIPE_WH_SECRET:
        # Caso pelirojo: API key set pero webhook secret no.
        # Atacante podria forjar eventos. Rechazamos firmemente.
        raise HTTPException(500,
            "production_misconfig: STRIPE_SECRET_KEY set but STRIPE_WEBHOOK_SECRET missing")

    if _stripe_demo_mode():
        # Demo SOLO en dev (STRIPE_KEY vacio). Acepta JSON sin firma con WARN.
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(400, "invalid_json")
        print(f"[webhook] DEMO MODE accepted unsigned event from {client_ip}",
              file=sys.stderr)
    else:
        try:
            import stripe
        except ImportError:
            raise HTTPException(500, "stripe package missing")
        try:
            # Issue #7 HIGH: catch ESPECIFICAMENTE SignatureVerificationError
            # (no Exception general que oculta timeouts/issues reales).
            event = stripe.Webhook.construct_event(
                payload, sig, STRIPE_WH_SECRET,
            )
        except stripe.error.SignatureVerificationError as e:
            print(f"[webhook] SIGNATURE_INVALID from {client_ip}: {e}",
                  file=sys.stderr)
            raise HTTPException(400, f"signature_invalid: {e}")
        except ValueError as e:
            # Payload malformado (no JSON), separar de signature fail
            raise HTTPException(400, f"payload_invalid: {e}")

    event_id = event.get("id", "")
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})
    raw_tenant_id = (obj.get("metadata") or {}).get("tenant_id") \
        or obj.get("client_reference_id")
    if not raw_tenant_id:
        return {"ok": True, "skipped": "no_tenant_id_in_event"}

    # Issue #4 HIGH: validar tenant_id antes de tocar filesystem o DB
    try:
        tenant_id = _validate_tenant_id(raw_tenant_id)
    except HTTPException as e:
        print(f"[webhook] REJECTED invalid tenant_id '{raw_tenant_id}' "
              f"from {client_ip}", file=sys.stderr)
        raise

    # Issue #6 MEDIUM: rechazar event_type no soportado explicitamente
    if event_type not in SUPPORTED_EVENT_TYPES:
        print(f"[webhook] UNSUPPORTED event_type '{event_type}' from "
              f"{client_ip} for tenant {tenant_id}", file=sys.stderr)
        return {"ok": True, "skipped": "unsupported_event_type",
                "event_type": event_type}

    db = _tenant_db(tenant_id)
    _ensure_stripe_cols(db)
    _ensure_idempotency_table(db)

    conn = sqlite3.connect(str(db), timeout=10)
    conn.isolation_level = None  # control transactions manualmente
    tx_open = False
    try:
        # Issue #5 HIGH + #9 MEDIUM audit2: BEGIN TRANSACTION atomica + flag
        conn.execute("BEGIN IMMEDIATE")
        tx_open = True

        # Issue #2 CRITICAL: idempotency check
        if event_id:
            row = conn.execute(
                "SELECT 1 FROM stripe_events_processed WHERE event_id = ?",
                (event_id,),
            ).fetchone()
            if row:
                conn.execute("COMMIT")
                print(f"[webhook] IDEMPOTENCY_SKIP event_id={event_id} "
                      f"tenant={tenant_id}", file=sys.stderr)
                # Issue #3 HIGH: NO devolver tenant_id en response
                return {"ok": True, "duplicate": True}

        if event_type == "checkout.session.completed":
            customer = obj.get("customer", "")
            sub_id = obj.get("subscription", "")
            plan = (obj.get("metadata") or {}).get("plan", "standard")
            # Validar plan tambien (defensa en profundidad)
            if plan not in PLAN_LIMITS:
                plan = "standard"
            conn.execute(
                "UPDATE tenant_meta SET plan=?, stripe_customer_id=?, "
                "stripe_subscription_id=?, stripe_subscription_status='active' "
                "WHERE tenant_id=?",
                (plan, customer, sub_id, tenant_id),
            )
        elif event_type in ("customer.subscription.updated",
                              "customer.subscription.created"):
            status = obj.get("status", "")
            period_end = obj.get("current_period_end")
            conn.execute(
                "UPDATE tenant_meta SET stripe_subscription_status=?, "
                "current_period_end=? WHERE tenant_id=?",
                (status, str(period_end) if period_end else None, tenant_id),
            )
        elif event_type == "customer.subscription.deleted":
            conn.execute(
                "UPDATE tenant_meta SET stripe_subscription_status='canceled', "
                "plan='standard' WHERE tenant_id=?",
                (tenant_id,),
            )
        elif event_type == "invoice.payment_failed":
            conn.execute(
                "UPDATE tenant_meta SET stripe_subscription_status='past_due' "
                "WHERE tenant_id=?",
                (tenant_id,),
            )
        elif event_type == "invoice.payment_succeeded":
            # No mutamos plan, solo extendemos period si viene
            period_end = obj.get("lines", {}).get("data", [{}])[0].get(
                "period", {}).get("end")
            if period_end:
                conn.execute(
                    "UPDATE tenant_meta SET current_period_end=? WHERE tenant_id=?",
                    (str(period_end), tenant_id),
                )

        # Marca event como procesado (anti-replay)
        if event_id:
            conn.execute(
                "INSERT INTO stripe_events_processed (event_id, event_type, "
                "tenant_id) VALUES (?, ?, ?)",
                (event_id, event_type, tenant_id),
            )

        conn.execute("COMMIT")
        tx_open = False

        # Issue #9 MEDIUM: audit log estructurado
        try:
            audit_log = (ROOT / "data" / "stripe_webhook.log")
            audit_log.parent.mkdir(parents=True, exist_ok=True)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            with audit_log.open("a", encoding="utf-8") as f:
                f.write(f"[{ts}] OK event={event_type} id={event_id} "
                        f"tenant={tenant_id} ip={client_ip}\n")
        except Exception:
            pass
    except Exception as e:
        # Issue #9 MEDIUM audit2: rollback condicional usando tx_open flag.
        # Si BEGIN nunca ejecuto (excepcion temprana), no intentamos ROLLBACK.
        if tx_open:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        print(f"[webhook] TX_FAIL tenant={tenant_id} event={event_type}: {e}",
              file=sys.stderr)
        raise HTTPException(500, "webhook_processing_failed")
    finally:
        conn.close()

    # Issue #3 HIGH: response minimalista (no eco datos sensibles)
    return {"ok": True, "event_type": event_type}


# ============================================================================
# Check de limites (helper para CFO)
# ============================================================================
def check_tenant_limits(tenant_id: str) -> dict:
    """Verifica si el tenant excedio su quota del plan. Usable desde CFO."""
    db = TENANTS_ROOT / tenant_id / "memory.db"
    if not db.exists():
        return {"ok": False, "error": "tenant_not_found"}
    conn = sqlite3.connect(str(db), timeout=5)
    try:
        cur = conn.execute(
            "SELECT plan FROM tenant_meta WHERE tenant_id = ?",
            (tenant_id,)
        )
        row = cur.fetchone()
        plan = (row[0] if row else "standard") or "standard"
        limits = PLAN_LIMITS.get(plan, {})

        actions_today = conn.execute(
            "SELECT COUNT(*) FROM action_log "
            "WHERE tenant_id = ? AND ts > datetime('now', '-1 day')",
            (tenant_id,)
        ).fetchone()[0]

        integrations = conn.execute(
            "SELECT COUNT(*) FROM api_credentials "
            "WHERE tenant_id = ? AND is_active = 1", (tenant_id,)
        ).fetchone()[0]

        max_actions = limits.get("actions_per_day")
        max_integrations = limits.get("integrations")
        return {
            "ok": True, "plan": plan,
            "actions_today": actions_today,
            "actions_limit": max_actions,
            "actions_remaining": (max_actions - actions_today
                                    if max_actions else None),
            "integrations": integrations,
            "integrations_limit": max_integrations,
            "quota_exceeded": (
                (max_actions is not None and actions_today >= max_actions)
                or (max_integrations is not None
                     and integrations > max_integrations)
            ),
        }
    finally:
        conn.close()
