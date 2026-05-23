# Jarvis Universal — Manifiesto de Arquitectura de Startup

> **Tesis**: un mismo core de software se vende a 100 industrias distintas si
> el code base separa **lo que el agente sabe** (vertical) de **cómo el agente
> ejecuta** (universal). Este documento describe cómo Jarvis V2 ya implementa
> esa separación a partir del 2026-05-23.

---

## 1. El insight clave

La mayoría de productos SaaS verticales son código duplicado: el "Shopify de
abogados", el "Shopify de plomeros", cada uno re-implementa autenticación,
billing, dashboard, integraciones... que son las **mismas primitivas**. Solo
cambia el **vocabulario**, los **workflows** específicos y los **integradores
externos**.

Jarvis explota esto. El core (graph + CFO + closed_loop + omniparser +
proxy OAuth) es **idéntico para todos los clientes**. Lo único que cambia
por cliente es:

1. **Persona** (system prompt del LLM): el vocabulario y el tono del experto
2. **Toolkit**: qué subset de skills/actions tiene permitidas
3. **Integraciones**: qué API keys de terceros tiene cacheadas (Shopify vs SAP)
4. **Memoria**: qué lecciones acumula sobre su industria

Esos 4 ejes son **archivos de configuración y filas en SQL**, no código.

---

## 2. Componentes verticales vs componentes universales

### 2.1 Universal (NO cambia entre clientes)

| Componente | Archivo | Función |
|---|---|---|
| State machine | `jarvis_v2/core/graph.py` | LangGraph: rag → planner → cfo → execute → verifier → halt |
| Planner | `node_planner` (graph.py) | Genera plan validado Pydantic con anti-condensación |
| CFO gateway | `jarvis_v2/cfo/cfo_evaluator.py` | Aprueba/deniega cada step (idempotency + spend) |
| Brain proxy | `jarvis_bridge/claude_proxy_fast.py` | OAuth Max raw HTTP, $0 |
| Closed-loop | `jarvis_v2/skills/closed_loop_controller.py` | execute_action_verified con SSIM |
| Visión semántica | `jarvis_v2/skills/omniparser_engine.py` | YOLO+Florence local, 672ms/76 elementos |
| Worker daemon | `jarvis_v2/task_worker.py` | Procesa queue 24/7 |
| API | `jarvis_v2/api/jarvis_api.py` | POST /execute /queue/add /tasks |
| Watchdog | `scripts/jarvis_watchdog.ps1` | Auto-revival cada 5 min |
| I+D perpetuo | `jarvis_v2/daemons/auto_researcher.py` | Cada 12h busca mejoras OmniParser/GUI |

### 2.2 Vertical (cambia entre clientes — pure configuration)

| Componente | Archivo | Función |
|---|---|---|
| **Industry Router** | `jarvis_v2/core/industry_router.py` | Clasifica input → carga máscara |
| **Industry config** | `INDUSTRIES` dict (mismo archivo) | system_prompt + allowed_actions + skills por vertical |
| **Multi-tenant DB** | `jarvis_v2/core/multi_tenant.sql` | Aislamiento empresa-A vs empresa-B |
| **Tenant memory** | `data/tenants/{tenant_id}/memory.db` | Lecciones, action log, spend ledger per-tenant |
| **Tenant secrets** | `data/tenants/{tenant_id}/secrets.enc` | API keys encriptadas (SOPS + age) |

---

## 3. Cómo funciona el enrutamiento dinámico (latencia <50ms)

```
Cliente:                "Mi tienda Shopify no esta cobrando, falta el token Admin"
                                       │
                                       ▼
              ┌─────────────────────────────────────────────┐
              │   industry_router.classify(text)            │
              │   - regex sobre keywords (instant)          │
              │   - 18 hits para 'ecommerce'                │
              │   - 0 hits para 'agri_logistics'            │
              │   → industry = "ecommerce"                  │
              └─────────────────────┬───────────────────────┘
                                    ▼
              ┌─────────────────────────────────────────────┐
              │   mask("ecommerce", tenant_id="acme-corp")  │
              │   carga:                                    │
              │   - system_prompt: "Eres experto e-commerce.│
              │     Stack: Shopify, AutoDS, Judge.me..."    │
              │   - allowed_actions: [shell, api, file_write,│
              │     browser_interact, marketing_campaign]   │
              │   - relevant_skills: [shopify-expert,       │
              │     ad-creative, revenue-operations]        │
              │   - tenant_db: data/tenants/acme-corp/      │
              │     memory.db                               │
              └─────────────────────┬───────────────────────┘
                                    ▼
              ┌─────────────────────────────────────────────┐
              │   node_planner usa mask.system_prompt        │
              │   + filtra actions a allowed_actions          │
              │   + carga lessons WHERE tenant_id=acme-corp  │
              └─────────────────────────────────────────────┘
```

**Tiempo total clasificación + carga máscara**: <50 ms (regex puro). Si los
keywords no matchean inequívocamente, hace 1 call a Haiku (~800ms, $0 via
OAuth Max).

---

## 4. Verticales soportadas hoy (extensible)

| Slug | Cliente típico | Vocabulario clave | Skills cargadas |
|---|---|---|---|
| **ecommerce** | Dueño tienda online | GMV, AOV, CAC, ROAS, abandoned cart | shopify-expert, ad-creative, grop-ecommerce |
| **agri_logistics** | Acopiadora granos | toneladas, humedad, merma, CFDI carta porte | neurograin-sap, fastapi-expert, pandas-pro |
| **marketing** | Agencia ads / growth | CTR, CPC, payback, attribution | ad-creative, campaign-analytics, growth-hacker |
| **dev** | Equipo de software | refactor, CI/CD, type safety | python-pro, react-expert, debugging-wizard |
| **video_pipeline** | Editor de contenido | ffmpeg, NVENC, loudnorm, sidechain ducking | manhwa-pipeline, remotion-expert |
| **trading** | Quant / trader | edge, drawdown, slippage, regime | bot-forex-analyst, pandas-pro |
| **generic** | Catch-all | — | general-purpose |

**Agregar una vertical nueva** = 1 entry en `INDUSTRIES`. Cero código. ~30 líneas.

---

## 5. Seguridad multi-tenant — garantías

### 5.1 Aislamiento de datos
- Cada tenant tiene su propio archivo `data/tenants/{id}/memory.db`. **Una empresa NO puede leer la BD de otra** porque el path es distinto y el filesystem no lo permite cross-tenant sin code change.
- `multi_tenant.sql` tiene `tenant_id` como PK compuesta o FK obligatoria en TODAS las tablas críticas: `tenant_meta`, `memory_lessons`, `api_credentials`, `action_log`, `spend_ledger`, `artifacts`.
- Toda query en application layer DEBE filtrar `WHERE tenant_id = ?`. **Nunca queries sin filtro de tenant**.

### 5.2 Aislamiento de secretos
- API tokens (Shopify, Meta, Binance, etc.) jamás viven en plaintext SQL.
- La tabla `api_credentials` solo guarda metadata + un `secret_ref` que apunta a `data/tenants/{id}/secrets.enc` (cifrado con SOPS + age).
- La master key de cada tenant es exclusiva. Rotación por tenant sin afectar otros.

### 5.3 Auditoría de cumplimiento
- `action_log` registra cada acción del agente con `ts`, `action_type`, `cost_usd`, `success`, `error`.
- Permite responder a SOC 2 / GDPR "qué hizo el sistema con mis datos el 15 de marzo a las 14:23".
- Spend ledger `spend_ledger` permite facturación por uso real al cliente final.

### 5.4 Permisos del agente
- `allowed_actions` por industria es un **whitelist**. El planner solo puede emitir steps con esas actions; cualquier otra → Pydantic rechaza.
- Ejemplo: cliente trading **no puede** emitir `youtube_upload`. Cliente video **no puede** emitir `binance_market_order`.

---

## 6. Pricing tiers sugeridos (modelo recurring)

| Plan | Precio MXN/mes | Uso típico | Límites |
|---|---|---|---|
| **Standard** | $1,499 | PyMe con 1 vertical | 1 tenant, 50 actions/día, 2 integraciones, memoria 30 días |
| **Pro** | $4,999 | Negocio con multi-canal | 1 tenant, 300 actions/día, 10 integraciones, memoria 1 año, soporte 24h |
| **Enterprise** | $14,999 + uso | Empresa con compliance | Tenants ilimitados, API ilimitada, on-prem opcional, SLA 99.9%, SOC 2 readiness |
| **White-label** | $49,999 + 10% rev | Agencias / partners | Branding propio, multi-tenant gestionado por el partner |

Costo marginal real por cliente: **0**. El proxy OAuth Max es flat. Solo si un cliente pide modelo Sonnet 4.6 alto-volumen, se factura overage a $X/Mtok.

---

## 7. Go-to-market — 3 demos pre-construidos

### Demo 1: E-commerce (cliente potencial: Bulmaro/Noé tienda)
Input: "Mi tienda Shopify no esta cobrando"
- Router clasifica → ecommerce
- Agente carga skill shopify-expert
- Genera plan: verificar token Admin API → setup correcto → upload imágenes → smoke test orden
- En 5 min: tienda operativa, 0 código manual

### Demo 2: Agri-logística (cliente potencial: acopiadora regional)
Input: "Concilía 3000 toneladas del silo norte vs facturas del mes"
- Router clasifica → agri_logistics
- Agente carga skill neurograin-sap + pandas-pro
- Genera plan: leer XLSX de remisiones → cross-join con facturas → detectar mermas anormales → report
- En 10 min: hoja Excel auditada con diferencias resaltadas

### Demo 3: Marketing (cliente potencial: agencia de PyMEs)
Input: "Lanza 5 creatives para Black Friday de cliente Z"
- Router clasifica → marketing
- Agente carga skill ad-creative + meta-ads-skill
- Genera plan: research competitor ads → generar 5 variants UGC → upload Meta Ads Manager
- En 30 min: 5 creatives en review, 0 horas-junior

---

## 8. Roadmap de escalabilidad — próximas 4 semanas

| Semana | Entregable | Métrica de éxito |
|---|---|---|
| 1 | Wrapper `tenant_session(tenant_id)` context manager en graph.py | Tests con 3 tenants concurrentes no leakean memoria |
| 2 | Dashboard web `/admin` por tenant | login → ver action_log + spend |
| 3 | Onboarding wizard: nuevo cliente → 1 comando crea tenant + secrets vault | <2 min de cero a primera acción |
| 4 | Self-serve signup con Stripe + plan tier | 1 cliente real pagando standard |

---

## 9. Por qué esta arquitectura gana

| Approach competidor | Limitación | Cómo Jarvis lo supera |
|---|---|---|
| SaaS vertical único (Klaviyo, Justifyhq, etc.) | Solo sirve a 1 industria | Mismo core sirve a 7+ verticales |
| RPA tradicional (UiPath, Automation Anywhere) | Costoso, requiere developers RPA | Self-driven, agentic, $0 LLM via OAuth |
| Chatbots verticales (Intercom, Ada) | Solo conversación, no ejecuta | Closed-loop con manos reales (GUI + APIs) |
| Open-source agents (AutoGPT, BabyAGI) | Sin multi-tenancy, sin CFO, sin verify | Production-ready: telemetría, isolation, watchdog |

---

## 10. Conclusión técnica

Jarvis no es "otro asistente AI". Es un **sistema operativo agéntico para
PyMEs y empresa**, donde la vertical se monta en runtime sin tocar el core.

Lo que ya funciona:
- ✅ Industry router con 7 verticales (validado 7/7 cases)
- ✅ Multi-tenant SQL schema con 6 tablas (aplicado a tenant `default`)
- ✅ Aislamiento por filesystem (`data/tenants/{id}/`)
- ✅ Telemetría por tenant (action_log + spend_ledger)
- ✅ Visión local CUDA $0 (OmniParser 672ms)
- ✅ Manos verificadas con SSIM (closed_loop_controller)
- ✅ 7 schtasks de auto-healing (watchdog, NTP, monitor swing, I+D perpetuo)

Lo que falta para vender el primer plan Standard:
- Wrapper tenant_session(tenant_id) en graph.py (3-4h dev)
- Dashboard admin minimal (1 día con shadcn)
- Stripe integration + onboarding (2 días)
- 1 cliente piloto firmado (sales)

**Tiempo realista de cero a primer revenue: 2 semanas.**

---

## Apéndice A — Comandos para validar la arquitectura HOY

```bash
# Smoke test classifier (7/7 pass esperado)
cd C:\Users\Emmanuel\Documents\JarvisAI
python -m jarvis_v2.core.industry_router

# Clasificar texto arbitrario + ver máscara cargada
python -m jarvis_v2.core.industry_router --text "Mi tienda Shopify rompió" --tenant acme-corp

# Listar verticales soportadas
python -m jarvis_v2.core.industry_router --list

# Ver estado de tenants
python -c "
import sqlite3
db = sqlite3.connect('data/tenants/default/memory.db')
for row in db.execute('SELECT * FROM v_tenant_summary'):
    print(row)
"
```
