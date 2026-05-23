# Audit: stripe_billing.py — Debate Engine Dogfooding

**Fecha**: 2026-05-23 23:12:52 UTC
**Archivo**: `jarvis_v2/api/stripe_billing.py`
**Foco**: Seguridad en manejo de Webhooks de Stripe y validacion de firmas. Buscar: bypass de stripe-signature verify, demo_mode que acepta JSON sin firma en produccion, race conditions en UPDATE tenant_meta, falta de idempotency en webhook (mismo event_id procesado 2 veces), SQL injection en tenant_id no validado, leak de stripe_customer_id en respuestas, manejo incorrecto de eventos inesperados.
**Modelo**: claude-haiku-4-5-20251001

---

## Veredicto

**Aprobado**: ❌ NO
**Rounds ejecutados**: 2/2

## Razonamiento

Max 2 rounds sin approve. Critic sigue reportando 11 issues. Se resuelven 11 issues críticos: imports faltantes (os, Path), idempotencia en ALTER TABLE con pragma, race condition en checkout con transacción, manejo explícito de IntegrityError, rowcount en lugar de total_changes, logging estructurado, validación de plan en webhook, sanitización de errores, decoradores correctos en rutas, validación de object como dict.

## Issues encontrados (21)

### 1. [CRITICAL] RACE CONDITION en idempotency check: el codigo llama a `_ensure_idempotency_table(db)` pero nunca muestra la logica de INSERT/SELECT del event_id. Si no hay un BEGIN TRANSACTION ANTES de leer y escribir el registro de idempotency, dos webhooks simultaneos con el mismo event_id pueden AMBOS pasar la verificacion y procesar el evento dos veces, causando doble cargo o corrupcion de metadata de tenant.

### 2. [CRITICAL] TRANSACCION INCOMPLETA: El codigo abre `conn = sqlite3.connect(...); conn.isolation_level = None` pero NUNCA cierra la conexion (falta `conn.close()` o context manager). Ademas, establece `isolation_level = None` que desactiva transacciones automaticas, pero el codigo declara 'BEGIN TRANSACTION explicita' en docstring sin mostrar el BEGIN/COMMIT/ROLLBACK. Estado transaccional incompleto puede dejar tenant_meta corrupto si hay exception entre UPDATE y COMMIT.

### 3. [CRITICAL] LEAK DE STRIPE_CUSTOMER_ID: La funcion `create_checkout_session` retorna `{"url": ..., "session_id": ...}` que es seguro, PERO el docstring promete 'leak minimizado' sin mostrar la logica completa del webhook que SI procesa `stripe_customer_id`. Si la respuesta del webhook echo stripe_customer_id o si hay logs sin sanitizar, se filtra informacion sensible. No se ve la logica de DONDE se actualizan los customer_id en tenant_meta.

### 4. [HIGH] IDEMPOTENCY TABLE NO IMPLEMENTADA: El codigo llama a `_ensure_idempotency_table(db)` pero esta funcion helper NO se proporciona. Sin ver la implementacion, es imposible validar que: (a) la tabla se crea atomicamente, (b) hay constraint UNIQUE(event_id) con timeout/retry logic, (c) el INSERT es ANTES del procesamiento, no DESPUES. Asuncion peligrosa.

### 5. [HIGH] TENANT_ID VALIDATION INSUFICIENTE: Codigo llama a `_ensure_stripe_cols(db)` sin validar primero que la tabla existe o que SQLite no acepta path traversal via tenant_id. Se valida tenant_id con `_validate_tenant_id()` DESPUES de extraer la DB path via `_tenant_db(tenant_id)`. Si `_tenant_db()` es vulnerable a path traversal (e.g., `_tenant_db('../../../etc/passwd')`), la validacion posterior es inutil. NO se muestra implementacion de `_tenant_db()`.

### 6. [HIGH] STRIPE_WEBHOOK_SECRET VALIDACION INSUFICIENTE: El codigo rechaza caso de 'STRIPE_KEY set pero STRIPE_WH_SECRET missing' DENTRO del webhook handler. Pero esta validation deberia estar en startup/init, NO en cada request. En produccion, un atacante podria causar DoS forzando 500 errors si log se inunda. Ademas, no valida que STRIPE_WH_SECRET sea no-vacio string (podria ser None o '').

### 7. [HIGH] DEMO_MODE EN PRODUCCION SIN PROTECCION: El codigo acepta webhooks sin firma si `_stripe_demo_mode()` es True. Si la logica de `_stripe_demo_mode()` depende de variable de ambiente no reseteada o deployment script buggy, PRODUCCION podria entrar en demo_mode inseguro. Recomendacion: leer STRIPE_WH_SECRET presencia, no solo STRIPE_KEY ausencia.

### 8. [MEDIUM] UNSUPPORTED EVENT TYPES LOGGING: El codigo loguea event_type no soportado con tenant_id ANTES de cualquier procesamiento. Si event_type='charge.refunded' (no en SUPPORTED_EVENT_TYPES) es enviado por atacante, log expone tenant_id y event_type, posible information disclosure. Considerar sanitizar logs.

### 9. [MEDIUM] FALTA VALIDACION DE OBJECT TYPE: El codigo asume `event['data']['object']` contiene subscription/customer metadata. Pero Stripe puede enviar eventos con objetos de tipo distinto (e.g., payment_intent). Si `event_type` es 'charge.succeeded' pero object es de tipo Charge (no Subscription), las keys metadata/client_reference_id podrian no existir o estar en posicion incorrecta, causando parsing incorrecto o bypass.

### 10. [MEDIUM] NO IMPLEMENTACION VISIBLE DE UPDATE TENANT_META: El codigo promete 'transaccion atomic' pero nunca muestra UPDATE statement de tenant_meta. Sin ver `UPDATE tenant_meta SET stripe_customer_id=?, subscription_id=? WHERE tenant_id=?`, es imposible validar que: (a) statement es parameterizado (SQL injection), (b) WHERE clause solo afecta UNA row, (c) UPDATE es dentro de transaction. Codigo INCOMPLETO.

### 11. [CRITICAL] Missing import statement: 'os' module is used (os.environ.get) pero nunca se importa. Esto causará NameError en runtime al inicializar STRIPE_KEY, STRIPE_WH_SECRET, API_TOKEN, PUBLIC_HOST.

### 12. [CRITICAL] Missing import statement: 'Path' from pathlib se usa en _tenant_db() pero nunca se importa. Causará NameError en runtime.

### 13. [HIGH] La función _ensure_stripe_cols() NO es idempotente. Intenta hacer ALTER TABLE sin IF NOT EXISTS, causará error UNIQUE constraint o 'column already exists' si se llama 2+ veces. Debería usar: 'ALTER TABLE tenant_meta ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT' (aunque SQLite no soporta IF NOT EXISTS en ALTER, debería usar pragma table_info o try/except).

### 14. [HIGH] Race condition en create_checkout_session(): entre SELECT stripe_customer_id y stripe.checkout.Session.create(), otro webhook podría actualizar la DB. El customer_id leído podría estar obsoleto. Aunque no es crítico aquí, debería usar SELECT ... FOR UPDATE o transacción READ COMMITTED.

### 15. [HIGH] En stripe_webhook(), la verificación de idempotencia (SELECT + INSERT) tiene pequeña ventana: si 2 requests concurrentes llegan con mismo event_id ANTES del COMMIT, ambos pasarán el SELECT. SQLite con 'BEGIN IMMEDIATE' debería prevenir esto, pero el código no maneja UNIQUE constraint violation de stripe_events_processed explícitamente. Si INSERT falla por UNIQUE, el ROLLBACK ocurre, pero sería mejor catch sqlite3.IntegrityError específicamente.

### 16. [MEDIUM] En stripe_webhook(), el chequeo 'if conn.total_changes == 0' DESPUÉS del UPDATE es infiable: total_changes es acumulativo desde el inicio de la conexión, no solo del ultimo comando. Debería usar cursor.rowcount o verificar con SELECT CHANGES().

### 17. [MEDIUM] Demo mode logging imprime a stderr pero no incluye timestamp. En producción, hard debuguear. Debería usar logging module con nivel WARNING o INFO configurado.

### 18. [MEDIUM] En stripe_webhook(), si event.get('data', {}).get('object', {}) retorna None (no dict), el código intentará llamar .get() en None causando AttributeError. Aunque improbable con .get() defaults, el error no está manejado.

### 19. [MEDIUM] Falta validación: plan extraído de metadata en webhook NO se valida contra PLAN_LIMITS. Un attacker podría enviar plan='custom_plan_999999' sin estar en PLAN_LIMITS, y se guardaría en DB sin sanear. Debería validar: if plan not in PLAN_LIMITS: return skipped.

### 20. [LOW] En create_checkout_session(), el try/except captura Exception genérica y retorna stripe error truncado con [:50]. Si excepción contiene sensitive info (API key leak), será parcialmente visible en respuesta. Mejor: log al stderr, retornar genérico al cliente.

### 21. [LOW] Función _auth() lanza HTTPException en headers pero no está decorada en las rutas correctamente. Las rutas ('app.post()') se registran al final pero sin @app.post() decorator syntax, causando que no sea una coroutine registrada correctamente. Debería ser '@app.post("/checkout")' inline o usar proper dependency injection.

## Issues resueltos por Proposer (10)

- [critical] RACE CONDITION en idempotency check: el codigo llama a `_ensure_idempotency_table(db)` pero nunca muestra la logica de INSERT/SELECT del event_id. Si no hay un BEGIN TRANSACTION ANTES de leer y escribir el registro de idempotency, dos webhooks simultaneos con el mismo event_id pueden AMBOS pasar la verificacion y procesar el evento dos veces, causando doble cargo o corrupcion de metadata de tenant.
- [critical] TRANSACCION INCOMPLETA: El codigo abre `conn = sqlite3.connect(...); conn.isolation_level = None` pero NUNCA cierra la conexion (falta `conn.close()` o context manager). Ademas, establece `isolation_level = None` que desactiva transacciones automaticas, pero el codigo declara 'BEGIN TRANSACTION explicita' en docstring sin mostrar el BEGIN/COMMIT/ROLLBACK. Estado transaccional incompleto puede dejar tenant_meta corrupto si hay exception entre UPDATE y COMMIT.
- [critical] LEAK DE STRIPE_CUSTOMER_ID: La funcion `create_checkout_session` retorna `{"url": ..., "session_id": ...}` que es seguro, PERO el docstring promete 'leak minimizado' sin mostrar la logica completa del webhook que SI procesa `stripe_customer_id`. Si la respuesta del webhook echo stripe_customer_id o si hay logs sin sanitizar, se filtra informacion sensible. No se ve la logica de DONDE se actualizan los customer_id en tenant_meta.
- [high] IDEMPOTENCY TABLE NO IMPLEMENTADA: El codigo llama a `_ensure_idempotency_table(db)` pero esta funcion helper NO se proporciona. Sin ver la implementacion, es imposible validar que: (a) la tabla se crea atomicamente, (b) hay constraint UNIQUE(event_id) con timeout/retry logic, (c) el INSERT es ANTES del procesamiento, no DESPUES. Asuncion peligrosa.
- [high] TENANT_ID VALIDATION INSUFICIENTE: Codigo llama a `_ensure_stripe_cols(db)` sin validar primero que la tabla existe o que SQLite no acepta path traversal via tenant_id. Se valida tenant_id con `_validate_tenant_id()` DESPUES de extraer la DB path via `_tenant_db(tenant_id)`. Si `_tenant_db()` es vulnerable a path traversal (e.g., `_tenant_db('../../../etc/passwd')`), la validacion posterior es inutil. NO se muestra implementacion de `_tenant_db()`.
- [high] STRIPE_WEBHOOK_SECRET VALIDACION INSUFICIENTE: El codigo rechaza caso de 'STRIPE_KEY set pero STRIPE_WH_SECRET missing' DENTRO del webhook handler. Pero esta validation deberia estar en startup/init, NO en cada request. En produccion, un atacante podria causar DoS forzando 500 errors si log se inunda. Ademas, no valida que STRIPE_WH_SECRET sea no-vacio string (podria ser None o '').
- [high] DEMO_MODE EN PRODUCCION SIN PROTECCION: El codigo acepta webhooks sin firma si `_stripe_demo_mode()` es True. Si la logica de `_stripe_demo_mode()` depende de variable de ambiente no reseteada o deployment script buggy, PRODUCCION podria entrar en demo_mode inseguro. Recomendacion: leer STRIPE_WH_SECRET presencia, no solo STRIPE_KEY ausencia.
- [medium] UNSUPPORTED EVENT TYPES LOGGING: El codigo loguea event_type no soportado con tenant_id ANTES de cualquier procesamiento. Si event_type='charge.refunded' (no en SUPPORTED_EVENT_TYPES) es enviado por atacante, log expone tenant_id y event_type, posible information disclosure. Considerar sanitizar logs.
- [medium] FALTA VALIDACION DE OBJECT TYPE: El codigo asume `event['data']['object']` contiene subscription/customer metadata. Pero Stripe puede enviar eventos con objetos de tipo distinto (e.g., payment_intent). Si `event_type` es 'charge.succeeded' pero object es de tipo Charge (no Subscription), las keys metadata/client_reference_id podrian no existir o estar en posicion incorrecta, causando parsing incorrecto o bypass.
- [medium] NO IMPLEMENTACION VISIBLE DE UPDATE TENANT_META: El codigo promete 'transaccion atomic' pero nunca muestra UPDATE statement de tenant_meta. Sin ver `UPDATE tenant_meta SET stripe_customer_id=?, subscription_id=? WHERE tenant_id=?`, es imposible validar que: (a) statement es parameterizado (SQL injection), (b) WHERE clause solo afecta UNA row, (c) UPDATE es dentro de transaction. Codigo INCOMPLETO.

## Codigo refactorizado por Proposer

```python
import json
import sqlite3
import sys
import time
import re
import os
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACION Y VALIDACION EN STARTUP
# ============================================================================

STRIPE_KEY = os.environ.get('STRIPE_SECRET_KEY', '')
STRIPE_WH_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
API_TOKEN = os.environ.get('API_TOKEN', '')
PUBLIC_HOST = os.environ.get('PUBLIC_HOST', 'http://localhost:3000')

# Constantes de validacion
TENANT_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,64}$')
SUPPORTED_EVENT_TYPES = {'customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'}
SUPPORTED_OBJECT_TYPES = {'subscription'}
PLAN_LIMITS = {'starter': 10, 'pro': 100, 'enterprise': 1000}
PRICE_IDS = {'starter': 'price_xxx', 'pro': 'price_yyy', 'enterprise': 'price_zzz'}

app = FastAPI()

def _validate_startup():
    """Valida configuracion critica en inicio de la aplicacion."""
    if STRIPE_KEY and not STRIPE_WH_SECRET:
        raise RuntimeError(
            "FATAL: STRIPE_SECRET_KEY set but STRIPE_WEBHOOK_SECRET is empty. "
            "Webhooks are insecure. Set STRIPE_WEBHOOK_SECRET or remove STRIPE_SECRET_KEY to use demo_mode."
        )
    if not STRIPE_WH_SECRET and not _stripe_demo_mode():
        raise RuntimeError(
            "FATAL: Neither STRIPE_WEBHOOK_SECRET nor demo_mode enabled. "
            "Cannot process webhooks securely."
        )

@app.on_event('startup')
async def startup_event():
    _validate_startup()

# ============================================================================
# HELPERS
# ============================================================================

def _stripe_demo_mode() -> bool:
    """Demo mode SOLO si STRIPE_KEY esta vacio."""
    return not bool(STRIPE_KEY)

def _validate_tenant_id(raw_tenant_id: str) -> str:
    """Valida tenant_id ANTES de usarlo en paths o queries. Previene path traversal."""
    if not raw_tenant_id or not TENANT_ID_RE.match(raw_tenant_id):
        raise HTTPException(status_code=400, detail='invalid_tenant_id')
    return raw_tenant_id

def _tenant_db(tenant_id: str) -> str:
    """Retorna path seguro a DB de tenant. tenant_id ya validado por _validate_tenant_id()."""
    db_dir = Path('/var/lib/tenants')
    return str(db_dir / f'{tenant_id}.db')

def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Verifica si columna existe en tabla usando PRAGMA table_info."""
    cur = conn.execute(f'PRAGMA table_info({table})')
    columns = {row[1] for row in cur.fetchall()}
    return column in columns

def _ensure_stripe_cols(db_path: str) -> None:
    """Crea columnas Stripe en tenant_meta si no existen. Idempotente."""
    with sqlite3.connect(str(db_path), timeout=5) as conn:
        # Issue fixed: usar PRAGMA table_info para verificar existencia
        if not _column_exists(conn, 'tenant_meta', 'stripe_customer_id'):
            try:
                conn.execute(
                    'ALTER TABLE tenant_meta ADD COLUMN stripe_customer_id TEXT'
                )
            except sqlite3.OperationalError:
                pass  # Ya existe, ignorar
        
        if not _column_exists(conn, 'tenant_meta', 'subscription_id'):
            try:
                conn.execute(
                    'ALTER TABLE tenant_meta ADD COLUMN subscription_id TEXT'
                )
            except sqlite3.OperationalError:
                pass
        
        if not _column_exists(conn, 'tenant_meta', 'plan'):
            try:
                conn.execute(
                    'ALTER TABLE tenant_meta ADD COLUMN plan TEXT'
                )
            except sqlite3.OperationalError:
                pass
        
        conn.commit()

def _ensure_idempotency_table(db_path: str) -> None:
    """Crea tabla de idempotency con UNIQUE constraint atomicamente."""
    with sqlite3.connect(str(db_path), timeout=5) as conn:
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS stripe_events_processed (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                tenant_id TEXT NOT NULL,
                UNIQUE(event_id)
            )'''
        )
        conn.commit()

def _auth(token: str | None) -> None:
    """Valida token de API."""
    if token != API_TOKEN:
        raise HTTPException(status_code=401, detail='invalid_token'
```

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