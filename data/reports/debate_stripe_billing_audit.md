# Audit: stripe_billing.py — Debate Engine Dogfooding

**Fecha**: 2026-05-23 23:01:41 UTC
**Archivo**: `jarvis_v2/api/stripe_billing.py`
**Foco**: Seguridad en manejo de Webhooks de Stripe y validacion de firmas. Buscar: bypass de stripe-signature verify, demo_mode que acepta JSON sin firma en produccion, race conditions en UPDATE tenant_meta, falta de idempotency en webhook (mismo event_id procesado 2 veces), SQL injection en tenant_id no validado, leak de stripe_customer_id en respuestas, manejo incorrecto de eventos inesperados.
**Modelo**: claude-haiku-4-5-20251001

---

## Veredicto

**Aprobado**: ❌ NO
**Rounds ejecutados**: 1/2

## Razonamiento

(sin razonamiento)

## Issues encontrados (10)

### 1. [CRITICAL] SQL injection en tenant_id: _validate_tenant_id() se llama pero su implementación no está presente en el código. Sin validación visible de TENANT_ID_RE, un tenant_id malicioso podría inyectar SQL en _tenant_db(tenant_id) que construye rutas/queries. Riesgo: path traversal o SQL injection en subsequent queries.

### 2. [CRITICAL] Race condition en idempotency check: El código menciona 'Issue #2 CRITICAL: idempotency via stripe_events_processed table' pero NO se ve la lógica de SELECT/INSERT de event_id. Sin BEGIN TRANSACTION IMMEDIATE y CHECK BEFORE INSERT, dos webhooks concurrentes con mismo event_id pueden ambos pasar la validación y procesar el evento dos veces, causando duplicate charges/subscriptions.

### 3. [CRITICAL] Transacción incompleta: conn.isolation_level = None activa autocommit, pero NO hay BEGIN TRANSACTION explícita ni commit(). El código se corta abruptamente sin mostrar cómo se actualiza tenant_meta (UPDATE stripe_customer_id, plan, etc). Sin lógica transaccional visible, UPDATE+INSERT pueden fallar parcialmente dejando estado corrupto.

### 4. [HIGH] Demo mode inseguro en producción: if _stripe_demo_mode() permite procesar eventos sin firma si STRIPE_KEY está vacío. Sin embargo, no hay validación explícita que _stripe_demo_mode() devuelva False en producción. Si por error STRIPE_KEY se borra en prod, webhooks se procesarían sin validar stripe-signature header, permitiendo forgery de eventos.

### 5. [HIGH] Leak de información en error messages: HTTPException(400, f'signature_invalid: {e}') expone detalles internos de Stripe SDK (stripe.error.SignatureVerificationError) al cliente. Atacante observa si firmas falladas son por formato, timing, o secret. Reducir a 'signature_invalid' sin detalles.

### 6. [HIGH] Manejo incorrecto de eventos inesperados: SUPPORTED_EVENT_TYPES no está definida en el código mostrado. Si está vacía o mal configurada, eventos críticos (subscription.updated, customer.deleted) podrían ser silenciosamente ignorados. Log dice 'skipped' pero no alerta sobre eventos que DEBERÍAN procesarse.

### 7. [MEDIUM] Falta validación de schema de 'obj' (event.data.object): No hay validación que obj contenga campos requeridos (id, metadata, client_reference_id). Si Stripe devuelve evento malformado, .get('metadata') devuelve None y (None).get() falla con TypeError no atrapado. Agregar try-except o schema validation (Pydantic).

### 8. [MEDIUM] Stripe API key validation débil: create_checkout_session() usa stripe.api_key = STRIPE_KEY sin validar formato. Si STRIPE_KEY='invalid', error solo aparece al llamar stripe.checkout.Session.create(). Validar format early o usar try-except específico para stripe.error.AuthenticationError.

### 9. [MEDIUM] Timeout en sqlite3.connect(str(db), timeout=10) insuficiente: Si otro proceso lockea la DB durante 10s, webhook falla. Sin retry logic, evento se pierde. Stripe reintentará, pero sin idempotency garantizada (ver issue #2), puede causar race. Implementar exponential backoff o connection pooling.

### 10. [LOW] Log de client_ip: En case de stripe_demo_mode, se loguea IP del cliente. Si un forward proxy, client.host puede ser proxy IP, no verdadera fuente. En producción, considerar usar X-Forwarded-For header con validación, o remover IP del log si no es crítica.

## Issues resueltos por Proposer (0)

_Ninguno (o no se necesitaron rondas adicionales)._

---

## Codigo auditado (extracto)

```python
def _auth(token: str | None) -> None:
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail="invalid_token")


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



async def stripe_webhook(request: Request):
    """Recibe events de Stripe: subscription created/updated/canceled.

    HARDENING tras dogfooding audit (5 issues CRITICAL+HIGH resueltos):
      #1 CRITICAL: demo_mode SOLO si STRIPE_SECRET_KEY ausente. Si esta set
         pero WH_SECRET falta -> 500, NO acepta JSON sin firma.
      #2 CRITICAL: idempotency via stripe_events_processed table.
      #3 HIGH:    leak minimizado en response (no eco de stripe_customer_id).
      #4 HIGH:    tenant_id validado con TENANT_ID_RE (path traversal block).
      #5 HIGH:    BEGIN TRANSACTION expli

... [3031 chars trimmed] ...
```