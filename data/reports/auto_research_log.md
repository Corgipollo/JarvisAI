# Auto Research Log — Bitacora del Problem Solver

> Daemon `auto_problem_solver.py` cada 60 min escanea bloqueadores
> activos del sistema, hace deep_research y sintetiza alternativas.
> Append-only. Lectura humana opcional.

---

## 2026-05-23 19:36:32 — [CRITICAL] debate_stripe_billing_audit.md

**Problema detectado**: demo_mode SOLO si STRIPE_SECRET_KEY ausente.

**Source research**: none (0 resultados, 5749ms)

### Sintesis

# Resolver demo_mode sin STRIPE_SECRET_KEY (2026)

## Alternativas Open Source Gratuitas

| Solución | Implementación | Costo | Dificultad |
|----------|----------------|-------|-----------|
| **Stripe Mock (local)** | `stripe-mock` CLI + `stripe-go` bindings. Simula respuestas reales sin conexión. | $0 | ⭐ Baja |
| **Adyen OpenAPI Mock** | Docker container con especificaciones OpenAPI para pagos. Ideal testing local. | $0 | ⭐⭐ Media |
| **Mollie Test Keys** | Credenciales de prueba con respuestas determinísticas. No requiere secreto real inicial. | $0 | ⭐ Baja |
| **Fallback a localStorage** | Guardar transacciones simuladas en cliente. Lógica condicional: `if(!STRIPE_SECRET_KEY) useLocalStorage()`. | $0 | ⭐ Baja |
| **PostgREST + PostgreSQL** | Backend mock con triggers SQL. Simula pagos sin procesador externo. | $0 | ⭐⭐⭐ Alta |
| **Fake API estática JSON** | Servidor mock (json-server/Mockoon). Retorna respuestas predefinidas por ruta. | $0 | ⭐ Baja |

## Recomendación rápida (hoy)
**Stripe Mock CLI** (2min setup): descarga binario, ejecuta `stripe-mock -port 12111`, apunta tu SDK a localhost. Es solución oficial de Stripe.

---

## 2026-05-23 19:36:43 — [CRITICAL] debate_stripe_billing_audit.md

**Problema detectado**: idempotency via stripe_events_processed table.

**Source research**: none (0 resultados, 7563ms)

### Sintesis

# Idempotency en Stripe: Soluciones Open Source 2026

## Patrón con `stripe_events_processed`
Almacenar `event.id` de Stripe en tabla + constraint UNIQUE previene duplicados. En webhook:
```sql
INSERT INTO stripe_events_processed (event_id, payload, processed_at) 
VALUES (?, ?, NOW()) ON CONFLICT DO NOTHING;
```

## 4 Alternativas Open Source Gratuitas

| Solución | Approach | Costo | Dificultad |
|----------|----------|-------|-----------|
| **Redis + Lua Scripts** | Cache con TTL (24h) de event IDs. Lua atomiza check-insert | Gratis (self-hosted) | Media |
| **PostgreSQL con LISTEN/NOTIFY** | Trigger en tabla + deduplicación automática con sequences | Gratis | Media-Alta |
| **Temporal.io** | Workflow engine con garantía de deduplicación nativa | Gratis (self-hosted) | Alta |
| **Apache Kafka + idempotent producer** | Partición por merchant_id, offset tracking por consumer group | Gratis | Alta |
| **SQLite + WAL mode** (microservicios) | PRAGMA journal_mode=WAL + UNIQUE constraint. Suficiente <10k events/día | Gratis | Baja |
| **Knack/Bull Queue** (Node.js) | Job queue con `attempts` + `backoff`, deduplicación por job ID | Gratis | Baja |

## Recomendación Pragmática 2026
**Redis + Lua** para <100k eventos/mes (simplicidad). **Temporal.io** si requieres audit trail y retries complejos. **SQLite+WAL** viable para MVP sin infra.

---

## 2026-05-23 19:37:26 — [CRITICAL] debate_stripe_billing_audit.md

**Problema detectado**: demo_mode SOLO si STRIPE_SECRET_KEY ausente.

**Source research**: none (0 resultados, 5123ms)

### Sintesis

# Solución: Activar demo_mode cuando falta STRIPE_SECRET_KEY

## Implementación recomendada

```python
# En tu archivo de configuración/inicialización
import os

STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
demo_mode = not bool(STRIPE_SECRET_KEY)
```

Esto activa automáticamente modo demo si la variable de entorno está ausente.

---

## 4 Alternativas Open Source gratuitas (2026)

| Alternativa | Coste | Dificultad | Caso de uso |
|---|---|---|---|
| **Medusa** (Node.js) | $0 | Moderada | Ecommerce completo, integrable con Stripe opcional |
| **Saleor** (GraphQL/Django) | $0 | Alta | Plataforma enterprise-grade, modo sandbox nativo |
| **Odoo Community** (Python) | $0 | Media-Alta | ERP + pagos, soporte de múltiples gateways |
| **WooCommerce + WP Offsite** | $0 (self-hosted) | Baja | WordPress, plugins gratuitos de pago simulado |

**Bonus rápido:** `Stripe Test Mode` (gratuito integrado) - usa claves `pk_test_` y `sk_test_` sin costos, es la opción más directa si ya usas Stripe.

---

**Recomendación inmediata:** Implementa la solución de env variable + usa Stripe Test Mode. Cero fricción, cero coste, lista hoy.

---

## 2026-05-23 19:37:35 — [CRITICAL] debate_stripe_billing_audit.md

**Problema detectado**: idempotency via stripe_events_processed table.

**Source research**: none (0 resultados, 5826ms)

### Sintesis

# Idempotency con Stripe: Soluciones Open Source

## Patrón stripe_events_processed

Crear tabla deduplicación de eventos Stripe:

```sql
CREATE TABLE stripe_events_processed (
  event_id VARCHAR(255) PRIMARY KEY,
  processed_at TIMESTAMP,
  result JSONB
);
```

Consultar antes de procesar cada webhook; si existe, retornar resultado cached.

---

## 4 Alternativas Open Source 2026

| Solución | Costo | Dificultad | Caso de uso |
|----------|-------|-----------|-----------|
| **PostgreSQL + pgBoss** | Gratis | Media | Queue + deduplicación nativa. pgBoss almacena `jobId` único por evento Stripe. |
| **Redis + Lua scripts** | Gratis (self-hosted) | Media-Alta | Deduplicación ultra-rápida con TTL. Script Lua garantiza atomicidad. |
| **Apache Kafka + idempotent producers** | Gratis (self-hosted) | Alta | Streaming masivo. Deduplicación por `transaction.id` nativo. |
| **SQLite + WAL mode** | Gratis | Baja | Proyectos pequeños/edge. No escalable pero simple y confiable. |

---

## Recomendación Inmediata (Hoy)

**PostgreSQL + tabla deduplicación** (tu enfoque):
- ✅ Implementable en <2 horas
- ✅ Costo: $0
- ✅ Agregar índice en `event_id` y consultar BEFORE INSERT
- ✅ Escala hasta ~1M eventos/día sin problemas

**Código mínimo:**
```python
# Webhook handler
event_id = event['id']
if not db.stripe_events_processed.filter(event_id=event_id).exists():
    process_event(event)
    db.stripe_events_processed.create(event_id=event_id, result={...})
```

---

## 2026-05-23 19:37:44 — [PENDIENTE] jarvis_omniparser_architecture.md

**Problema detectado**: Descargar OmniParser weights → `models/omniparser/`

**Source research**: none (0 resultados, 5228ms)

### Sintesis

# Alternativas Open Source a OmniParser (2026)

## Problema
OmniParser requiere descargar weights (~2-5GB) manualmente. Las alternativas modernas evitan esto.

## Soluciones Accionables

| Alternativa | Costo | Dificultad | Por Qué |
|---|---|---|---|
| **Claude Vision API** | $0-20/mes (pay-as-you-go) | ⭐ Muy bajo | No requiere pesos locales. Mejor OCR + UI parsing. Setup: `pip install anthropic` |
| **PaddleOCR + Tesseract** | Gratis | ⭐⭐ Bajo | OCR puro sin ML pesado. Para extracción texto/tablas. Alternativa ligera |
| **Ollama + LLaVA** | Gratis | ⭐⭐⭐ Moderado | Descarga automática de modelos (~7GB). `ollama pull llava` → visión local |
| **YOLOv8 + EasyOCR** | Gratis | ⭐⭐⭐ Moderado | Detección UI + OCR. Weights auto-descargan. Más rápido que OmniParser |
| **Hugging Face Spaces** | Gratis | ⭐ Muy bajo | Ejecuta modelos sin instalar nada. Copiar código demostración |

## Recomendación 2026
**Para hoy:** Claude Vision + PaddleOCR (híbrido). Claude para lógica, PaddleOCR offline para OCR puro.
**Para flujos offline:** Ollama + LLaVA (mejor relación costo-rendimiento local).

¿Cuál es tu caso de uso específico (Web scraping, documentos, interfaces)?

---

