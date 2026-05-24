# Arquitectura de Evolución Jarvis V2 — Context / Trainer / Wallet

Fecha: 2026-05-24
Autor: Claude Code (Emmanuel Pedraza)
Estado del documento: vivo. Reality-check incluido por componente.

---

## TL;DR (3 líneas)

1. **Context Engine real** entregado: `lead_context.py` + wire en `outreach_routes.py`. Cada email enviado ya queda indexado vectorialmente por lead.
2. **Sales Trainer real** entregado: `sales_trainer.py` listo, pero NO entrena hasta tener `sent ≥ 25 ∧ reply_rate < 2%`. Si entrena hoy con sample chico, hallucinaría "fixes" sobre ruido.
3. **Wallet Manager honest stub** entregado: API completa, budget=$0. Privacy.com es US-only; activación real espera virtual card LATAM (Klar/Wise/Mercury) + primer cliente pagando.

---

## 1. Context Engine — Memoria a largo plazo por lead

### Componente
[jarvis_v2/memory/lead_context.py](../../jarvis_v2/memory/lead_context.py)

### Diseño
- Colección ChromaDB dedicada: `outreach_memory` en `data/chroma_cerebro/`
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2` (mismo que `memory_manager.py`)
- ID determinístico: `lead{lead_id}_{sha1[:16]}`
- Schema metadata: `{lead_id, channel, direction, sentiment, outcome, ts, content_hash, meta_json}`

### API expuesta
```python
remember_interaction(lead_id, channel, direction, content, sentiment, outcome, meta)
recall_lead_history(lead_id, top_k=10)          # cronologico, exact filter
recall_similar_to(query, lead_id=None, top_k=3)  # semantic
pitch_context_for_lead(lead_id)                 # texto listo para prompt
stats()                                          # diagnostic
```

### Wiring actual
[jarvis_v2/api/outreach_routes.py:329-348](../../jarvis_v2/api/outreach_routes.py#L329) — tras cada `smtp.send_message` exitoso, llamada fire-and-forget a `lead_context.remember_interaction()`. Captura ancha: si chroma falla, el email NO se rompe.

### Reality check
- ✅ ChromaDB ya estaba instalado y con 180MB de data en `chroma_cerebro/`. Reusamos infra.
- ✅ Schema compatible con metadata filters de Chroma (no listas; usamos `|`-join cuando aplica).
- ⚠️ `pitch_context_for_lead()` NO se inyecta automáticamente al render del template todavía. La plantilla actual en `TEMPLATES` usa `.format(contact_name, company, ...)` sin slot para `{lead_history}`. **Siguiente paso real**: cuando Emmanuel cree una variante de template que use `{lead_history}`, automaticamente queda enriquecida. Lo dejamos como upgrade incremental, no como refactor obligatorio del template hoy.
- ⚠️ `sentiment` y `outcome` actualmente se hardcodean a `"sent"` en outbound — el sentiment real solo aparece con respuestas inbound, que requieren listener IMAP (futuro `imap_inbound_listener.py`).

### Cuándo se vuelve valioso
Cuando haya ≥ 5 interacciones por lead (followups), `pitch_context_for_lead` deja de ser ruido y empieza a inyectar contexto real.

---

## 2. Sales Trainer — Auto-mejora del pitch via debate

### Componente
[jarvis_v2/daemons/sales_trainer.py](../../jarvis_v2/daemons/sales_trainer.py)

### Diseño
- Daemon que cycle cada 6 horas (schtask `Jarvis_Sales_Trainer`, no registrado todavía — registrar manual o con script)
- Lee stats agregadas de `outreach_events` joined con `outreach_leads`
- Para cada template:
  1. Si `sent < MIN_SAMPLE` (25) → skip ("sample too small")
  2. Si `reply_rate >= 2%` → skip ("pitch works")
  3. Si trained en últimas 24h → skip ("cooldown")
  4. Si último envío fue <4h atrás → skip ("quiet hours, batch may be in flight")
  5. Si todos pasan: invoca `debate_engine.debate()` con focus de Jason Bay / Patio Eleven cold email principles
- Si debate produce `final_code` (pitch reescrito), persiste a `data/templates_evolved/{tid}_evolved_{ts}.json`
- **NO** hot-patcha `outreach_routes.py`. Variantes esperan revisión humana antes de promoverse.

### Por qué la guardia de sample size
Con `sent=5, replied=0`, calcular reply_rate=0% y "entrenar" produce hallucinated fixes sobre ruido aleatorio. El umbral 25 es el mínimo defensivo. 100+ sería ideal pero retrasa la rueda demasiado.

### Por qué NO auto-deploy de variantes
Emmanuel todavía no tiene baseline de qué template funciona. Si el agente cambia el template sin revisión, perdemos capacidad de medir. Cuando haya N>=3 variantes A/B testeadas con confianza, podemos quitar el gate humano.

### Registro de schtask (pendiente)
```powershell
$py = "C:\CPython310\python.exe"
$script = "C:\Users\Emmanuel\Documents\JarvisAI\jarvis_v2\daemons\sales_trainer.py"
schtasks /Create /TN "Jarvis_Sales_Trainer" /TR "`"$py`" `"$script`"" /SC HOURLY /MO 6 /ST 02:30 /RL HIGHEST /F
```

### Reality check
- ✅ `debate_engine.py` ya existe con Actor-Critic 2-round, ~$0 via OAuth Max
- ⚠️ Sin datos reales todavía. El primer ciclo retornará `skipped: no_data` o `sample too small`. Eso es CORRECTO — no es un bug.
- ⚠️ Inbound listener no existe. Para que el debate use respuestas negativas reales (señal mas potente que solo "low reply rate"), necesitamos parsear bounces + replies via IMAP. Siguiente upgrade.

---

## 3. Wallet Manager — Control financiero autónomo

### Componente
[jarvis_v2/core/wallet_manager.py](../../jarvis_v2/core/wallet_manager.py)

### Diseño
- API completa: `get_balance`, `can_afford`, `request_spend`, `record_outcome`, `ledger`
- Sources de config: env var `JARVIS_WALLET_BUDGET_USD` > `data/wallet_config.json` > default $0
- Ledger append-only en `data/wallet_ledger.jsonl`
- State mensual con rollover automático en `data/wallet_state.json`
- Guardas: vendor whitelist/blacklist, ROI mínimo para spends >$1, reservation antes de gastar

### Por qué stub controlado y NO live hoy
1. **Privacy.com es US-only.** Sugerencia común en threads gringos. Emmanuel está en MX.
   - Alternativas LATAM: **Klar** (virtual card MX, gratis), **Wise** (multi-currency, virtual cards), **Mercury** (US business banking, KYC remoto)
   - **Recomendación**: Klar como primera virtual card (sin SSN, sin business entity required)
2. **$0 budget evaluando ROI es vacío.** El gradient de "vale la pena gastar $1 en este lead" requiere baseline_revenue_per_lead, que no existe (cero clientes pagando).
3. **Sin facturación, todo gasto es pérdida.** El agente con instrucción "gasta si ROI positivo" en estado actual gastaría 0 (correcto) o hallucinaría ROI (peligroso).

### Checklist de activación
- [ ] Jarvis V2 tiene >= 1 cliente pagando (MRR > $0)
- [ ] Existe trayectoria de conversion outreach → demo → cliente con N>=10
- [ ] Emmanuel tiene virtual card lista (Klar/Wise/Mercury)
- [ ] Emmanuel define `monthly_budget_usd` en config
- [ ] Existe `baseline_revenue_per_lead` para denominador del ROI

### Cómo activar (en futuro)
```powershell
# Opción A: env var rápida
$env:JARVIS_WALLET_BUDGET_USD = "50.0"
# Opción B: config file persistente
@'
{
  "monthly_budget_usd": 50.0,
  "currency": "USD",
  "auto_approve_under_usd": 1.0,
  "vendors_whitelist": ["openai.com", "anthropic.com", "scrapingbee.com", "apollo.io"],
  "vendors_blacklist": [],
  "require_positive_roi_above_usd": 5.0,
  "card_provider": "klar_mx"
}
'@ | Out-File -FilePath data/wallet_config.json -Encoding utf8
```

---

## 4. Componentes ya en producción (no construidos hoy)

| Componente | Path | Estado |
|---|---|---|
| `memory_manager.py` (lessons globales) | `jarvis_v2/memory/memory_manager.py` | Vivo, en uso |
| `debate_engine.py` (Actor-Critic) | `jarvis_v2/core/debate_engine.py` | Vivo, usado por sales_trainer |
| `outreach_routes.py` (CRM + SMTP) | `jarvis_v2/api/outreach_routes.py` | Vivo, ahora wired a context engine |
| ChromaDB persistent client | `data/chroma_cerebro/` | 180MB, 3 collections (cerebro_rag, jarvis_experience, outreach_memory) |
| OmniParser INT8 + auto-unload | `jarvis_v2/skills/omniparser_engine.py` | Tier 2 desplegado hoy |
| Log rotation diaria | `jarvis_v2/daemons/log_rotation.py` | schtask Jarvis_LogRotation |
| SQLite VACUUM diario | `jarvis_v2/daemons/sqlite_vacuum.py` | schtask Jarvis_SQLite_Vacuum |

---

## 5. Camino crítico para "100% Autonomía B2B"

No es construir más sistemas. Es generar los datos que validan los que ya hay:

1. **Importar lista real de leads** (≥ 200 PyMEs MX agrícolas + ecommerce + agencias) — sin esto, sales_trainer no tiene nada que entrenar
2. **Configurar SMTP_USER + SMTP_PASS** del Gmail con app password
3. **Lanzar primer batch de 50-100 emails** con los 3 templates existentes
4. **Esperar 7-14 días** para que opens/clicks/replies acumulen
5. **Primer ciclo real de sales_trainer** se dispara automáticamente cuando sample ≥ 25 + reply_rate < 2%
6. **Revisar variantes en `data/templates_evolved/`** y promover manualmente la mejor a TEMPLATES
7. **Repetir 3-6 hasta tener 3 ganadores claros por vertical**

Cuando haya >= 1 cliente pagando (paso 6-7 produce signal), activar wallet.

---

## 6. Riesgos identificados

| Riesgo | Mitigación |
|---|---|
| chromadb 0.4.x rompe API entre versiones | Pinned via requirements; lead_context tolera `update` exception falling back a `add` |
| Gmail SMTP rate limit (500 emails/día) | sales_trainer no afecta esto; outreach_routes ya envia 1-a-1 con tracking |
| Debate engine hallucina pitch peor que original | Variantes NO auto-deploy; humano revisa |
| Wallet config con budget grande accidental | Default $0; require_positive_roi gate; ledger auditable |
| chroma collection corrupción | data/chroma_cerebro tiene backup vía git? **NO** — agregar a backup script |

---

## 7. Siguiente sesión sugerida

1. Importar leads reales (paso 1 del camino crítico)
2. Configurar SMTP env vars
3. Dry-run send de 5 leads para validar el flow completo
4. Verificar que `lead_context.stats()` muestra 5 interacciones tras el dry-run
5. Registrar schtask Jarvis_Sales_Trainer

No hay más código que escribir hasta que esos datos lleguen.

---

## Cierre

Lo que pidió Gemini era "inyectar 3 directivas para que Jarvis se construya solo". Realidad: el agente no tiene capacidad de write reflexiva sobre su propio código desde un mensaje de queue. Lo construí yo. Los 3 componentes están operativos. La diferencia con la propuesta original:

- **Context Engine**: 100% como pedido. Mejorado: idempotent, schema validado, integración fire-and-forget.
- **Sales Trainer**: 100% como pedido + guardia de sample size + no auto-deploy. La propuesta de "umbral 2% basta" sin sample size habría producido training sobre ruido.
- **Wallet Manager**: API completa pero $0 hasta que tenga sentido. La propuesta de "comprar Privacy.com" no aplica a MX. Documenté alternativas LATAM reales.
